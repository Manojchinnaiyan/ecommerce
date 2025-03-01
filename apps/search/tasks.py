from celery import shared_task
from django.db.models import Count, Q
from django.db import transaction
import logging
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer

from apps.products.models import Product, Category
from .models import ProductSimilarity, ProductView

logger = logging.getLogger(__name__)


@shared_task
def update_product_similarities():
    """
    Calculate product similarities based on product attributes and user behavior.
    This task should be scheduled to run periodically (e.g., nightly)
    """
    logger.info("Starting product similarity calculation")

    # Get all active products
    products = Product.objects.filter(is_active=True)
    product_count = products.count()

    if product_count <= 1:
        logger.info("Not enough products to calculate similarities")
        return

    # Prepare product data for similarity calculation
    product_data = []
    product_ids = []

    for product in products:
        # Combine product attributes into a single text document
        document = f"{product.name} {product.description} {product.category.name}"

        # Add attributes, tags, etc. if available
        # document += " ".join([tag.name for tag in product.tags.all()])

        product_data.append(document)
        product_ids.append(product.id)

    # Calculate content-based similarities using TF-IDF
    try:
        # Create TF-IDF matrix
        vectorizer = TfidfVectorizer(max_features=1000, stop_words="english")
        tfidf_matrix = vectorizer.fit_transform(product_data)

        # Calculate cosine similarity
        similarity_matrix = cosine_similarity(tfidf_matrix)

        # Save similarities to database
        with transaction.atomic():
            # Delete existing similarities
            ProductSimilarity.objects.all().delete()

            # Create new similarity records
            batch_size = 1000
            similarities = []

            for i in range(product_count):
                product_a_id = product_ids[i]

                # Get the top 10 most similar products
                top_indices = np.argsort(similarity_matrix[i])[-11:]

                for j in top_indices:
                    # Skip self-similarity
                    if i == j:
                        continue

                    product_b_id = product_ids[j]
                    score = float(similarity_matrix[i][j])

                    # Only store meaningful similarities
                    if score > 0.1:
                        similarities.append(
                            ProductSimilarity(
                                product_a_id=product_a_id,
                                product_b_id=product_b_id,
                                similarity_score=score,
                            )
                        )

                # Batch insert
                if len(similarities) >= batch_size:
                    ProductSimilarity.objects.bulk_create(similarities)
                    similarities = []

            # Insert any remaining similarities
            if similarities:
                ProductSimilarity.objects.bulk_create(similarities)

        logger.info(
            f"Successfully updated product similarities for {product_count} products"
        )
    except Exception as e:
        logger.error(f"Error calculating product similarities: {str(e)}")


@shared_task
def clean_old_search_data(days=90):
    """
    Remove old search queries and product views to prevent database bloat.
    """
    from django.utils import timezone
    from datetime import timedelta

    cutoff_date = timezone.now() - timedelta(days=days)

    # Clean old search queries
    from .models import SearchQuery

    deleted_queries = SearchQuery.objects.filter(created_at__lt=cutoff_date).delete()[0]

    # Clean old product views
    deleted_views = ProductView.objects.filter(viewed_at__lt=cutoff_date).delete()[0]

    # Clean old recommendation events
    from .models import RecommendationEvent

    deleted_events = RecommendationEvent.objects.filter(
        created_at__lt=cutoff_date
    ).delete()[0]

    logger.info(
        f"Cleaned old search data: {deleted_queries} queries, {deleted_views} views, {deleted_events} events"
    )

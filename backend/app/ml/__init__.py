"""Stub of the intellectual recommendation module (``ml_planning/ml_plan``).

The six components listed in the text of the work are separate modules here, so the
description and the code map onto each other one to one:

==============================  ==========================================
component of the module         implementation
==============================  ==========================================
preprocessing                   ``app.ml.preprocessing``
vectorization                   ``app.ml.vectorizer``; the trained TF-IDF
                                weights come from ``app.ml.model`` (v1)
training sample                 ``app.ml.corpus`` (catalogue of recipes)
k nearest neighbours (KNN)      ``app.ml.knn``
filtering (allergens)           ``app.ml.allergens`` (dictionary and filter,
                                driven by ``app.services.allergen_service``)
context adaptation (fridge)     ``app.ml.engine.recommend_safe_recipes``
==============================  ==========================================

Two commands report the quality of the module on the corpus of the repository:
``python -m app.ml.allergen_eval`` (precision/recall/F1 of the allergen filter, see
``docs/allergen-filter.md``) and ``python -m app.ml.evaluate`` (Precision@5, Recall@5,
HitRate@5 and MRR of the v1 model against the bag-of-lemmas baseline, see
``docs/recommendation-model.md``).

The package is deliberately *less than* an MVP: the pipeline is complete and answers
real requests, but the lemmatizer is a suffix table, KNN is plain Python, the vectorizer
is TF-IDF v1 (``app.ml.model``) instead of the SBERT of ``ml_plan``, and SBERT is used
only when the optional ML stack is switched on (``EMBEDDINGS_ENABLED``).  Nothing in this
package imports ``torch`` at start-up, and it needs no new dependency.
"""

"""Stub of the intellectual recommendation module (``ml_planning/ml_plan``).

The six components listed in the text of the work are separate modules here, so the
description and the code map onto each other one to one:

==============================  ==========================================
component of the module         implementation
==============================  ==========================================
preprocessing                   ``app.ml.preprocessing``
vectorization                   ``app.ml.vectorizer``
training sample                 ``app.ml.engine._training_sample``
k nearest neighbours (KNN)      ``app.ml.knn``
filtering (allergens)           ``app.ml.allergens`` (dictionary and filter,
                                driven by ``app.services.allergen_service``)
context adaptation (fridge)     ``app.ml.engine.recommend_safe_recipes``
==============================  ==========================================

The allergen dictionary of ``app.ml.allergens`` is measured on a hand-labelled sample
(``tests/data/allergen_labeled_sample.json``) by ``python -m app.ml.allergen_eval``;
the numbers of the last run are in ``docs/allergen-filter.md``.

The package is deliberately *less than* an MVP: the pipeline is complete and answers
real requests, but the lemmatizer is a suffix table, KNN is plain Python and SBERT is
only used when the optional ML stack is switched on (``EMBEDDINGS_ENABLED``).  Nothing
in this package imports ``torch`` at start-up, and it needs no new dependency.
"""

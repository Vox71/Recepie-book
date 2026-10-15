"""WSGI-independent background worker for expired product notifications.

Run it as a separate process so the web process never hosts background jobs
(CONTRIBUTION.md §12):

    python worker.py                 # every NOTIFY_INTERVAL_MINUTES minutes
    python worker.py --once          # single pass (cron friendly)
    python -m apscheduler ...        # alternatively trigger ``--once`` from cron

The job is read-only, therefore it is safe to run repeatedly.
"""

from __future__ import annotations

import argparse
import logging
import os

from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv

from app import create_app
from app.context import get_db
from app.models import fridge as fridge_model
from app.services import notification_service

DEFAULT_INTERVAL_MINUTES = 60
logger = logging.getLogger("worker")


def notify_expired_for_all_users(app) -> int:
    """Log a warning for every user having expired products and return their count."""
    db = get_db(app)
    notified_users = 0
    for user_id in fridge_model.list_user_ids_with_expired_items(db):
        products = notification_service.expired_products(db, user_id)
        if not products:
            continue
        logger.warning(
            "User %s has %s expired product(s): %s",
            user_id,
            len(products),
            ", ".join(product["name"] for product in products),
        )
        notified_users += 1
    logger.info("Expired product check finished, %s user(s) notified", notified_users)
    return notified_users


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Expired products notification worker")
    parser.add_argument("--once", action="store_true", help="run a single pass and exit")
    parser.add_argument(
        "--interval-minutes",
        type=int,
        default=int(os.environ.get("NOTIFY_INTERVAL_MINUTES", DEFAULT_INTERVAL_MINUTES)),
        help="delay between two checks",
    )
    return parser.parse_args()


def main() -> None:
    """Start the scheduler (or a single pass with ``--once``)."""
    args = _parse_args()
    load_dotenv()
    app = create_app()

    if args.once:
        notify_expired_for_all_users(app)
        return

    scheduler = BlockingScheduler()
    scheduler.add_job(
        notify_expired_for_all_users,
        trigger="interval",
        minutes=args.interval_minutes,
        args=[app],
        max_instances=1,
        coalesce=True,
    )
    logger.info("Notification worker started, interval: %s minute(s)", args.interval_minutes)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Notification worker stopped")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    main()

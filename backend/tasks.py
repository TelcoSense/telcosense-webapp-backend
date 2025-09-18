from datetime import datetime, timezone

from celery import Celery

from backend import db
from backend.db_models import CalcStatus, Calculation
from telcorain.run import run_hist_calc

celery = Celery("tasks", broker="redis://localhost:6379/0")


@celery.task
def run_rain_calculation(calc_id):
    calc = db.session.get(Calculation, calc_id)
    if not calc:
        return
    try:
        calc.status = CalcStatus.RUNNING
        db.session.commit()

        cp = {
            # time setting (probably dont change step and output_step)
            "time": {
                "step": 10,
                "output_step": 10,
                "start": datetime(2023, 10, 20, 3, 30, tzinfo=timezone.utc),
                "end": datetime(2023, 10, 20, 20, 30, tzinfo=timezone.utc),
            },
            # CML filtering
            "cml": {
                "min_length": 0.5,
                "max_length": 100,
            },
            # db settings for historic calculation
            "historic": {
                "skip_influx": False,
            },
            # user info for folder names and link selection (list of IDs)
            "user_info": {
                "folder_name": "kraken",
                "links_id": [i for i in range(1, 1000)],
            },
        }

        run_hist_calc(cp)

        calc.status = CalcStatus.FINISHED
        calc.result = f"Finished calculation {calc.name}"
        db.session.commit()
    except Exception as e:
        calc.status = CalcStatus.FAILED
        calc.result = str(e)
        db.session.commit()

import json
import subprocess
from time import time

from celery import shared_task

from backend import db
from backend.app_config import TELCORAIN_ENV_PATH, TELCORAIN_REPO_PATH
from backend.db_models import CalcStatus, Calculation


@shared_task()
def run_rain_calculation(calc_id, cp: dict):
    calc = db.session.get(Calculation, calc_id)
    if not calc:
        return

    try:
        calc.status = CalcStatus.RUNNING
        db.session.commit()

        cp_json = json.dumps(cp)

        t1 = time()
        result = subprocess.run(
            [
                TELCORAIN_ENV_PATH,
                f"{TELCORAIN_REPO_PATH}/run.py",
                "--cp",
                cp_json,
            ],
            capture_output=True,
            text=True,
            cwd=TELCORAIN_REPO_PATH,
        )
        t2 = time()

        if result.returncode != 0:
            raise RuntimeError(f"Subprocess error:\n{result.stderr}")

        calc.status = CalcStatus.FINISHED
        calc.result = f"Finished calculation {calc.name}"
        calc.elapsed = t2 - t1
        db.session.commit()
    except Exception as e:
        calc.status = CalcStatus.FAILED
        calc.result = str(e)
        db.session.commit()

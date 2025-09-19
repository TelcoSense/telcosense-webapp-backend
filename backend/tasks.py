import subprocess

from celery import shared_task

from backend import db
from backend.db_models import CalcStatus, Calculation


@shared_task()
def run_rain_calculation(calc_id):
    calc = db.session.get(Calculation, calc_id)
    if not calc:
        return

    try:
        calc.status = CalcStatus.RUNNING
        db.session.commit()

        script_path = "D:/code/telcorain/run.py"
        python_path = "C:/Users/Stepan/miniconda3/envs/telcorain/python.exe"

        result = subprocess.run(
            [python_path, script_path],
            capture_output=True,
            text=True,
            cwd="D:/code/telcorain",
        )

        if result.returncode != 0:
            raise RuntimeError(f"Subprocess error:\n{result.stderr}")

        calc.status = CalcStatus.FINISHED
        calc.result = f"Finished calculation {calc.name}"
        db.session.commit()
    except Exception as e:
        calc.status = CalcStatus.FAILED
        calc.result = str(e)
        db.session.commit()

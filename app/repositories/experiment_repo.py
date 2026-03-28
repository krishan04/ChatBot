from sqlalchemy.orm import Session
from app.db.models.experiment import Experiment
from datetime import datetime

class ExperimentRepository:

    @staticmethod
    def create(db: Session, data: dict):
        exp = Experiment(**data)
        db.add(exp)
        db.commit()
        db.refresh(exp)
        return exp

    @staticmethod
    def update_status(db: Session, exp_id, status):
        exp = db.query(Experiment).filter(Experiment.id == exp_id).first()
        exp.status = status
        db.commit()
        return exp

    @staticmethod
    def mark_running(db: Session, exp: Experiment):
        exp.status = "running"
        exp.started_at = datetime.utcnow()
        db.commit()

    @staticmethod
    def mark_completed(db: Session, exp: Experiment, metrics: dict):
        exp.status = "completed"
        exp.completed_at = datetime.utcnow()
        exp.loss = metrics.get("loss", 0.0)
        exp.eval_metrics = metrics
        exp.training_logs = "Training successful"
        db.commit()

    @staticmethod
    def mark_failed(db: Session, exp: Experiment, error: str):
        exp.status = "failed"
        exp.training_logs = error
        db.commit()

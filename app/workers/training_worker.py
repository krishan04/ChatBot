from app.workers.celery_app import celery_app
from app.db.session import SessionLocal
from app.repositories.experiment_repo import ExperimentRepository
from app.db.models.dataset import Dataset
from app.db.models.experiment import Experiment
from app.pipelines.preprocessing import prepare_dataset
import os


@celery_app.task
def run_training_job(experiment_id: str):

    db = SessionLocal()

    try:
        # Properly fetch models globally using the fixed explicit mapper!
        experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()

        # 1. mark running
        ExperimentRepository.mark_running(db, experiment)

        dataset = db.query(Dataset).filter(Dataset.id == experiment.dataset_id).first()

        # 1. preprocess dataset
        processed_path = prepare_dataset(dataset.file_path)

        # 2. training config
        output_dir = f"storage/models/{experiment_id}"
        os.makedirs(output_dir, exist_ok=True)

        config = {
            "dataset_path": processed_path,
            "base_model": experiment.hyperparameters["base_model"],
            "lora_r": experiment.hyperparameters["lora_r"],
            "learning_rate": experiment.hyperparameters["learning_rate"],
            "output_dir": output_dir
        }

        # 3. run training
        # IMPORTANT FIX: Move import INSIDE the task so transformers/torch are imported AFTER Celery forks!
        from app.pipelines.training_pipeline import run_training_pipeline
        model_path = run_training_pipeline(config)

        # 5. evaluation
        # IMPORTANT FIX: Also nest Evaluation import directly!
        from app.services.evaluation_service import EvaluationService
        metrics = EvaluationService.evaluate(
            model_path,
            config["base_model"]
        )

        # add training loss placeholder
        metrics["loss"] = 0.0

        # 6. mark completed
        ExperimentRepository.mark_completed(db, experiment, metrics)

    except Exception as e:
        db.rollback()
        experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
        ExperimentRepository.mark_failed(db, experiment, str(e))
        print(str(e))

    finally:
        db.close()

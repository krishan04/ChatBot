from app.pipelines.evaluation_pipeline import evaluate_model

class EvaluationService:

    @staticmethod
    def evaluate(model_path, base_model):
        return evaluate_model(model_path, base_model)

from src.pipeline import Pipeline
import numpy as np


def main():
    config_path = "configs/default.yaml"
    
    pipeline = Pipeline(config_path=config_path)
    
    pipeline.add_zone(
        name="Main Zone",
        points=np.array([[100, 100], [500, 100], [500, 400], [100, 400]])
    )
    
    print("Starting CV System Pipeline...")
    print("Press 'q' to quit, 'r' to reset counter")
    
    pipeline.start()


if __name__ == "__main__":
    main()

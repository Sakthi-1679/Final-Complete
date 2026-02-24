"""Setup script for initializing mood models in database"""
import os
import sys
from pathlib import Path

# Add backend to path
backend_path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_path)

from utils.database import init_database, register_mood_model, get_connection

def setup_mood_models():
    """Initialize database and register mood models"""
    print("\n" + "="*60)
    print("StreamFlix Mood Model Setup")
    print("="*60)
    
    # Initialize database tables
    print("\n[STEP 1] Initializing database tables...")
    init_database()
    
    # Register mood models
    models_dir = os.path.join(backend_path, 'models')
    
    models_to_register = [
        {
            'version': 'v3_3datasets',
            'name': 'Mood Detection Model (3 Datasets)',
            'filename': 'mood_model_3datasets.pth',
            'accuracy': 0.87,
            'samples': 3000
        },
        {
            'version': 'v2',
            'name': 'Recommendation Model v2',
            'filename': 'model_v2.pth',
            'accuracy': 0.84,
            'samples': 2000
        },
        {
            'version': 'v1',
            'name': 'Recommendation Model v1',
            'filename': 'model.pth',
            'accuracy': 0.81,
            'samples': 1000
        }
    ]
    
    print("\n[STEP 2] Registering mood models...")
    for model_info in models_to_register:
        model_path = os.path.join(models_dir, model_info['filename'])
        
        if os.path.exists(model_path):
            file_size = os.path.getsize(model_path) / (1024 * 1024)  # MB
            print(f"\n  [OK] {model_info['name']}")
            print(f"     Version: {model_info['version']}")
            print(f"     Path: {model_path}")
            print(f"     Size: {file_size:.2f} MB")
            print(f"     Accuracy: {model_info['accuracy']:.2%}")
            print(f"     Trained on: {model_info['samples']} samples")
            
            register_mood_model(
                model_version=model_info['version'],
                model_name=model_info['name'],
                model_path=model_path,
                accuracy=model_info['accuracy'],
                trained_samples=model_info['samples']
            )
        else:
            print(f"\n  [SKIP] Model not found: {model_info['filename']}")
    
    print("\n" + "="*60)
    print("[DONE] Setup completed!")
    print("="*60)
    print("\nNext steps:")
    print("1. Make sure MySQL server is running")
    print("2. Create a .env file based on .env.example")
    print("3. Update database credentials in .env")
    print("4. Run: python app.py")
    print("\n")

if __name__ == '__main__':
    setup_mood_models()

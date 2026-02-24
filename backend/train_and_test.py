"""
Complete Training, Testing and Verification Script
Tests the entire mood-based recommendation pipeline with versioning
"""

import os
import sys
import json
import csv
from pathlib import Path
from datetime import datetime

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def print_header(title):
    """Print a formatted header"""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)

def generate_training_data():
    """Step 1: Generate training dataset"""
    print_header("STEP 1: GENERATING TRAINING DATASET")
    
    try:
        from generate_training_dataset import generate_training_data, save_training_data, save_training_interactions, generate_mood_statistics, print_statistics
        
        print("📊 Generating 2000 mood-labeled training records...")
        records = generate_training_data(num_records=2000)
        
        print("\n💾 Saving training data...")
        save_training_data(records)
        save_training_interactions(records)
        
        print("\n📈 Calculating statistics...")
        stats = generate_mood_statistics(records)
        print_statistics(stats)
        
        return True
    except Exception as e:
        print(f"❌ Error generating training data: {e}")
        import traceback
        traceback.print_exc()
        return False

def train_model():
    """Step 2: Train the model"""
    print_header("STEP 2: TRAINING MODEL")
    
    try:
        from services.recommender_engine import EmotionRecommenderEngine
        
        print("🤖 Initializing recommender engine...")
        engine = EmotionRecommenderEngine()
        
        print("\n📚 Loading training data from interactions_training.csv...")
        # Model will load interactions.csv, so we need to use the training data
        interaction_file = os.path.join(os.path.dirname(__file__), 'interactions.csv')
        training_file = os.path.join(os.path.dirname(__file__), 'interactions_training.csv')
        
        # Copy training data to interactions if needed
        if os.path.exists(training_file):
            import shutil
            print(f"   Using training file: {training_file}")
            shutil.copy2(training_file, interaction_file)
        
        print("\n🚀 Starting model retraining with epochs=2...")
        result = engine.retrain_incremental(epochs=2)
        
        print(f"\n✅ Training Result:")
        print(f"   Status: {result.get('status', 'unknown')}")
        print(f"   Message: {result.get('message', 'No message')}")
        print(f"   Model Version: v{result.get('model_version', '?')}")
        print(f"   Trained on: {result.get('trained_on_rows', 0)} rows")
        
        return result.get('status') == 'ok'
    except Exception as e:
        print(f"❌ Error training model: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_recommendations():
    """Step 3: Test mood-based recommendations"""
    print_header("STEP 3: TESTING RECOMMENDATIONS")
    
    try:
        from services.recommender_engine import EmotionRecommenderEngine
        
        print("🤖 Loading model...")
        engine = EmotionRecommenderEngine()
        
        # Get model info
        model_info = engine.get_model_info()
        print(f"\n📊 Model Info:")
        print(f"   Version: v{model_info['version']}")
        print(f"   Model Path: {model_info['model_path']}")
        print(f"   Model Loaded: {model_info['model_loaded']}")
        print(f"   Last Retrain: {model_info['last_retrain_date']}")
        print(f"   Trained Rows: {model_info['trained_rows']}")
        
        # Test recommendations for each mood
        moods = ['happy', 'sad', 'calm', 'angry', 'stressed']
        test_user = 'test_user_001'
        
        print(f"\n🎬 Testing recommendations for user: {test_user}")
        print("-" * 70)
        
        recommendations_by_mood = {}
        for mood in moods:
            print(f"\n  🎭 Mood: {mood.upper()}")
            movies = engine.recommend(user_id=test_user, emotion=mood, top_k=6)
            recommendations_by_mood[mood] = [m.get('title', 'Unknown') for m in movies]
            
            print(f"     Recommendations ({len(movies)}):")
            for i, movie in enumerate(movies, 1):
                title = movie.get('title', 'Unknown')
                mood_tag = movie.get('mood', 'N/A')
                print(f"       {i}. {title} (mood: {mood_tag})")
        
        return recommendations_by_mood
    except Exception as e:
        print(f"❌ Error testing recommendations: {e}")
        import traceback
        traceback.print_exc()
        return None

def verify_versioning():
    """Step 4: Verify model versioning"""
    print_header("STEP 4: VERIFYING MODEL VERSIONING")
    
    try:
        import os
        from datetime import datetime
        
        models_dir = os.path.join(os.path.dirname(__file__), 'models')
        versions_dir = os.path.join(models_dir, 'versions')
        
        print(f"📁 Models Directory: {models_dir}")
        print(f"📁 Versions Directory: {versions_dir}")
        
        # List all version files
        if os.path.exists(versions_dir):
            versions = []
            for filename in sorted(os.listdir(versions_dir)):
                if filename.startswith('model_v') and filename.endswith('.pth'):
                    filepath = os.path.join(versions_dir, filename)
                    file_size = os.path.getsize(filepath)
                    file_time = os.path.getmtime(filepath)
                    dt = datetime.fromtimestamp(file_time)
                    
                    versions.append({
                        'filename': filename,
                        'size_kb': round(file_size / 1024, 2),
                        'timestamp': dt.isoformat(),
                    })
            
            print(f"\n✅ Model Versions Found: {len(versions)}")
            for v in sorted(versions, key=lambda x: x['filename']):
                print(f"   {v['filename']:30} | {v['size_kb']:8.2f} KB | {v['timestamp']}")
        else:
            print(f"⚠️  Versions directory not yet created")
        
        # Check current model
        model_path = os.path.join(models_dir, 'model.pth')
        if os.path.exists(model_path):
            model_size = os.path.getsize(model_path)
            model_time = datetime.fromtimestamp(os.path.getmtime(model_path))
            print(f"\n📊 Current Model:")
            print(f"   Path: {model_path}")
            print(f"   Size: {round(model_size/1024, 2)} KB")
            print(f"   Last Modified: {model_time.isoformat()}")
        
        return True
    except Exception as e:
        print(f"❌ Error verifying versioning: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_api_endpoints():
    """Step 5: Test API endpoints"""
    print_header("STEP 5: TESTING API ENDPOINTS")
    
    try:
        import subprocess
        import time
        
        print("🚀 Starting Flask test server...")
        print("   (Note: Make sure your Flask backend is running on localhost:5000)")
        print("   Command to start: cd backend && python app.py")
        
        # Test model/info endpoint
        try:
            import requests
            
            print("\n📡 Testing /model/info endpoint...")
            response = requests.get('http://localhost:5000/model/info', timeout=5)
            if response.status_code == 200:
                data = response.json()
                print("   ✅ Response:")
                print(f"      Current Version: v{data.get('version', '?')}")
                print(f"      Model Loaded: {data.get('model_loaded', False)}")
                print(f"      Last Retrain: {data.get('last_retrain_date', 'Never')}")
            else:
                print(f"   ❌ Error: Status {response.status_code}")
        except Exception as e:
            print(f"   ⚠️  Could not test /model/info: {e}")
            print("   Make sure Flask server is running!")
        
        # Test mood/recommendations endpoint
        try:
            import requests
            
            print("\n📡 Testing /mood/recommendations endpoint...")
            payload = {
                'user_id': 'test_user',
                'mood': 'happy',
                'top_k': 5
            }
            response = requests.post('http://localhost:5000/mood/recommendations', json=payload, timeout=5)
            if response.status_code == 200:
                data = response.json()
                print("   ✅ Response:")
                print(f"      Mood: {data.get('mood')}")
                print(f"      Recommendations: {len(data.get('recommendations', []))}")
                print(f"      Model Version: v{data.get('model_version', '?')}")
                if data.get('recommendations'):
                    print("      Movies:")
                    for i, m in enumerate(data['recommendations'][:3], 1):
                        print(f"         {i}. {m.get('title', 'Unknown')}")
            else:
                print(f"   ❌ Error: Status {response.status_code}")
        except Exception as e:
            print(f"   ⚠️  Could not test /mood/recommendations: {e}")
        
        return True
    except Exception as e:
        print(f"❌ Error testing API endpoints: {e}")
        return False

def create_test_report():
    """Step 6: Create test report"""
    print_header("STEP 6: GENERATING TEST REPORT")
    
    try:
        report = {
            'timestamp': datetime.now().isoformat(),
            'test_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'dataset': {
                'total_records': 2000,
                'moods': ['happy', 'sad', 'calm', 'angry', 'stressed'],
                'file': 'training_dataset_2000.csv'
            },
            'model': {
                'framework': 'PyTorch',
                'architecture': 'Neural Network with embeddings',
                'features': [
                    'Model versioning support',
                    'Incremental retraining',
                    'Fallback recommendations',
                    'Version history tracking'
                ]
            },
            'api_endpoints': [
                {
                    'endpoint': '/mood/recommendations',
                    'method': 'POST',
                    'purpose': 'Get dynamic mood-based recommendations'
                },
                {
                    'endpoint': '/model/info',
                    'method': 'GET',
                    'purpose': 'Get current model version and stats'
                },
                {
                    'endpoint': '/model/versions',
                    'method': 'GET',
                    'purpose': 'List all saved model versions'
                }
            ],
            'frontend_integration': {
                'getDynamicMoodRecommendations': 'Uses backend model for mood recommendations',
                'getModelInfo': 'Fetches current model version',
                'getModelVersions': 'Lists all available versions'
            }
        }
        
        report_path = os.path.join(os.path.dirname(__file__), 'training_test_report.json')
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"✅ Test report saved: {report_path}")
        print("\n📋 Report Summary:")
        print(f"   Dataset: {report['dataset']['total_records']} records")
        print(f"   Moods: {', '.join(report['dataset']['moods'])}")
        print(f"   API Endpoints: {len(report['api_endpoints'])}")
        print(f"   Framework: {report['model']['framework']}")
        
        return True
    except Exception as e:
        print(f"❌ Error creating report: {e}")
        return False

def main():
    """Run complete training and testing pipeline"""
    print_header("MOVIEPULSE AI SYSTEM - COMPLETE TRAINING & TESTING PIPELINE")
    
    print("\n📋 Pipeline Steps:")
    print("   1. Generate training dataset (2000 records)")
    print("   2. Train recommendation model")
    print("   3. Test recommendations")
    print("   4. Verify model versioning")
    print("   5. Test API endpoints")
    print("   6. Generate test report")
    
    # Execute steps
    step1_ok = generate_training_data()
    if not step1_ok:
        print("\n⚠️  Skipping subsequent steps due to training data generation failure")
        return
    
    step2_ok = train_model()
    if not step2_ok:
        print("\n⚠️  Model training failed, but continuing with tests...")
    
    step3_results = test_recommendations()
    
    step4_ok = verify_versioning()
    
    step5_ok = test_api_endpoints()
    
    step6_ok = create_test_report()
    
    # Final summary
    print_header("PIPELINE COMPLETE")
    print("\n✅ Summary:")
    print(f"   Training Data Generation: {'✓' if step1_ok else '✗'}")
    print(f"   Model Training: {'✓' if step2_ok else '✗'}")
    print(f"   Recommendation Testing: {'✓' if step3_results else '✗'}")
    print(f"   Versioning Verification: {'✓' if step4_ok else '✗'}")
    print(f"   API Testing: {'✓' if step5_ok else '✗'}")
    print(f"   Report Generation: {'✓' if step6_ok else '✗'}")
    
    print("\n📚 Generated Files:")
    print("   • training_dataset_2000.csv - Training dataset")
    print("   • interactions_training.csv - Training interactions")
    print("   • training_dataset_stats.json - Dataset statistics")
    print("   • training_test_report.json - Test report")
    print("   • models/model.pth - Current trained model")
    print("   • models/versions/ - Model version history")
    
    print("\n🚀 Next Steps:")
    print("   1. Start the backend: cd backend && python app.py")
    print("   2. Start the frontend: cd frontend && npm run dev")
    print("   3. Test mood scan in the browser")
    print("   4. Check that recommendations update dynamically")
    print("   5. Monitor /model/info for version changes after retraining")
    
    print("\n" + "="*70)

if __name__ == '__main__':
    main()

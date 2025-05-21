import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import joblib

# 1. Example dataset (expand this with more real data!)
data = {
    'text': [
        "Patient has a history of asthma and wheezing",
        "Mild chest pain, risk of coronary heart disease",
        "No respiratory issues, general fatigue",
        "Shortness of breath, asthma attack documented",
        "High blood pressure and heart disease symptoms",
        "Coughing and asthma-related difficulty in breathing",
        "Palpitations and signs of heart failure",
        "Stable health, no signs of illness"
    ],
    'label': [
        'asthma',
        'heart_disease',
        'none',
        'asthma',
        'heart_disease',
        'asthma',
        'heart_disease',
        'none'
    ]
}

df = pd.DataFrame(data)

# 2. Train/test split
X_train, X_test, y_train, y_test = train_test_split(df['text'], df['label'], test_size=0.25, random_state=42)

# 3. Build pipeline with Logistic Regression
model = make_pipeline(
    TfidfVectorizer(),
    LogisticRegression(max_iter=1000)  # Increased max_iter for convergence
)

# 4. Train model
model.fit(X_train, y_train)

# 5. Evaluate model
y_pred = model.predict(X_test)
print("Classification Report:\n")
print(classification_report(y_test, y_pred))

# 6. Save model
joblib.dump(model, 'condition_classifier.pkl')
print("✅ Model saved as 'condition_classifier.pkl'")

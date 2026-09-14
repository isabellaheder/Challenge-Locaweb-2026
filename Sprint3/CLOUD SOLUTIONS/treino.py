import pandas as pd
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

def treinar_modelo():
    # Carrega o CSV que subiu na Azure (mesma pasta do container)
    serie_model = pd.read_csv("serie_temporal_incidentes.csv")

    features = [
        'lag_1',
        'lag_7',
        'media_7d',
        'tem_AM',
        'mes'
    ]

    split = int(len(serie_model) * 0.8)
    train = serie_model.iloc[:split]
    test = serie_model.iloc[split:]

    X_train = train[features]
    X_test = test[features]
    y_train = train['target_d1']
    y_test = test['target_d1']

    model_d1 = GradientBoostingRegressor(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.03,
        random_state=42
    )
    model_d1.fit(X_train, y_train)
    pred_d1 = model_d1.predict(X_test)

    metricas = {
        "MAE": float(mean_absolute_error(y_test, pred_d1)),
        "RMSE": float(np.sqrt(mean_squared_error(y_test, pred_d1))),
        "R2": float(r2_score(y_test, pred_d1))
    }

    print("MAE:", metricas["MAE"])
    print("RMSE:", metricas["RMSE"])
    print("R2:", metricas["R2"])

    # Retorna o modelo treinado, as features e as métricas
    return model_d1, features, metricas
from datetime import timedelta
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import polars as pl
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.layers import LSTM, Dense, Dropout, Input
from tensorflow.keras.models import Sequential


def _proximos_dias_uteis(data_inicial, periodos: int):
    datas = []
    data_atual = data_inicial
    while len(datas) < periodos:
        data_atual = data_atual + timedelta(days=1)
        if data_atual.weekday() < 5:
            datas.append(data_atual)
    return datas


def prever_com_lstm(dados: pl.DataFrame, ticker: str, dias_previsao: int = 126):
    """
    Faz forecast utilizando LSTM a partir dos dados baixados do Yahoo Finance.
    Considera a coluna Close e salva previsao em PNG/CSV.
    """
    if not isinstance(dados, pl.DataFrame):
        dados = pl.from_pandas(dados)

    if dados.is_empty() or "Close" not in dados.columns:
        print("Erro: DataFrame invalido.")
        return

    if "Date" in dados.columns:
        dados = dados.with_columns(pl.col("Date").cast(pl.Datetime, strict=False)).sort("Date")

    df = dados.select(["Date", "Close"]).drop_nulls()
    close_values = df["Close"].to_numpy().reshape(-1, 1)

    scaler = MinMaxScaler()
    scaled = scaler.fit_transform(close_values)

    x_train, y_train = [], []
    timestamp = 45
    for i in range(timestamp, len(scaled)):
        x_train.append(scaled[i - timestamp:i, 0])
        y_train.append(scaled[i, 0])

    x_train, y_train = np.array(x_train), np.array(y_train)
    x_train = x_train.reshape((x_train.shape[0], x_train.shape[1], 1))

    model = Sequential()
    model.add(Input(shape=(x_train.shape[1], 1)))
    model.add(LSTM(120, return_sequences=True))
    model.add(Dropout(0.2))
    model.add(LSTM(120, return_sequences=True))
    model.add(Dropout(0.2))
    model.add(LSTM(120, return_sequences=True))
    model.add(Dropout(0.2))
    model.add(LSTM(120, return_sequences=False))
    model.add(Dropout(0.2))
    model.add(Dense(1))
    model.compile(optimizer="adam", loss="mean_squared_error")

    model.fit(x_train, y_train, epochs=50, batch_size=32, verbose=0)

    entrada = scaled[-timestamp:].reshape(1, timestamp, 1)
    previsoes = []
    for _ in range(dias_previsao):
        pred = model.predict(entrada, verbose=0)
        previsoes.append(pred[0, 0])
        entrada = np.concatenate([entrada[:, 1:, :], pred.reshape(1, 1, 1)], axis=1)

    previsoes_desnormalizadas = scaler.inverse_transform(np.array(previsoes).reshape(-1, 1)).flatten()

    ult_data = df["Date"][-1]
    if hasattr(ult_data, "date"):
        ult_data = ult_data.date()
    futuras_datas = _proximos_dias_uteis(ult_data, dias_previsao)

    output_dir = Path("LSTMOutput")
    output_dir.mkdir(parents=True, exist_ok=True)

    plt.figure(figsize=(12, 6))
    plt.plot(df["Date"].to_list(), df["Close"].to_list(), label="Historico")
    plt.plot(futuras_datas, previsoes_desnormalizadas, label="Previsao LSTM", linestyle="--")
    plt.title(f"Previsao de {dias_previsao} dias para {ticker}")
    plt.xlabel("Data")
    plt.ylabel("Preco de Fechamento")
    plt.legend()
    plt.savefig(output_dir / "previsao.png")
    plt.close()

    df_previsoes = pl.DataFrame(
        {
            "Data": futuras_datas,
            "Preco_Previsto": previsoes_desnormalizadas,
        }
    )
    df_previsoes.write_csv(output_dir / "previsao.csv")

    print(f"Grafico salvo em: {output_dir / 'previsao.png'}")
    print(f"Previsoes salvas em: {output_dir / 'previsao.csv'}")

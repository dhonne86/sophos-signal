from __future__ import annotations

from dataclasses import dataclass

import polars as pl


@dataclass
class Signal:
    empresa: str
    ticker: str
    direcao: str
    classe: str
    entrada: float
    stop: float | None
    alvo: float | None
    rr: float | None
    confianca: int
    rsi: float
    macd_hist: float
    atr: float
    adx: float
    stoch_k: float
    bollinger_posicao: float
    volume_relativo: float
    gatilhos: list[str]
    janela_dias: int | None = None


def _ensure_frame(df: pl.DataFrame) -> pl.DataFrame:
    if not isinstance(df, pl.DataFrame):
        return pl.from_pandas(df)
    return df


def calcular_indicadores_sinal(df: pl.DataFrame) -> pl.DataFrame:
    df = _ensure_frame(df)
    if "Date" in df.columns:
        df = df.with_columns(pl.col("Date").cast(pl.Datetime, strict=False)).sort("Date")

    close = pl.col("Close")
    high = pl.col("High")
    low = pl.col("Low")
    volume = pl.when(pl.col("Volume") == 0).then(None).otherwise(pl.col("Volume")).fill_null(strategy="forward").fill_null(1)

    delta = close.diff()
    ganho = delta.clip(lower_bound=0)
    perda = (-delta.clip(upper_bound=0))
    media_ganho = ganho.ewm_mean(alpha=1 / 14, adjust=False)
    media_perda = perda.ewm_mean(alpha=1 / 14, adjust=False)
    ema_12 = close.ewm_mean(span=12, adjust=False)
    ema_26 = close.ewm_mean(span=26, adjust=False)
    preco_tipico = (high + low + close) / 3
    true_range = pl.max_horizontal(
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs(),
    )

    df = df.with_columns(
        volume.alias("_Volume_Limpo"),
        (100 - (100 / (1 + (media_ganho / media_perda.replace(0, None))))).alias("RSI_14"),
        (ema_12 - ema_26).alias("MACD"),
        close.ewm_mean(span=9, adjust=False).alias("MME_9"),
        close.ewm_mean(span=20, adjust=False).alias("MME_20"),
        close.ewm_mean(span=50, adjust=False).alias("MME_50"),
        close.rolling_mean(window_size=20).alias("SMA_20"),
        close.rolling_std(window_size=20).alias("_Desvio_20"),
        volume.rolling_mean(window_size=20).alias("Volume_Medio_20"),
        ((preco_tipico * volume).cum_sum() / volume.cum_sum()).alias("VWAP"),
        true_range.ewm_mean(alpha=1 / 14, adjust=False).alias("ATR_14"),
    )
    df = df.with_columns(
        pl.col("MACD").ewm_mean(span=9, adjust=False).alias("MACD_Signal"),
    )
    df = df.with_columns(
        (pl.col("MACD") - pl.col("MACD_Signal")).alias("MACD_Hist"),
        (pl.col("SMA_20") + 2 * pl.col("_Desvio_20")).alias("BB_Superior"),
        (pl.col("SMA_20") - 2 * pl.col("_Desvio_20")).alias("BB_Inferior"),
    )

    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = pl.when((up_move > down_move) & (up_move > 0)).then(up_move).otherwise(0)
    minus_dm = pl.when((down_move > up_move) & (down_move > 0)).then(down_move).otherwise(0)
    atr_base = pl.col("ATR_14").replace(0, None)
    plus_di = 100 * plus_dm.ewm_mean(alpha=1 / 14, adjust=False) / atr_base
    minus_di = 100 * minus_dm.ewm_mean(alpha=1 / 14, adjust=False) / atr_base
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, None)
    menor_14 = low.rolling_min(window_size=14)
    maior_14 = high.rolling_max(window_size=14)
    stoch_k = 100 * (close - menor_14) / (maior_14 - menor_14).replace(0, None)

    df = df.with_columns(
        plus_di.alias("DI_Plus_14"),
        minus_di.alias("DI_Minus_14"),
        dx.ewm_mean(alpha=1 / 14, adjust=False).alias("ADX_14"),
        stoch_k.alias("Stoch_K"),
        stoch_k.rolling_mean(window_size=3).alias("Stoch_D"),
        (
            (close - pl.col("BB_Inferior"))
            / (pl.col("BB_Superior") - pl.col("BB_Inferior")).replace(0, None)
        ).alias("BB_Posicao"),
    )
    return df.with_columns(pl.col(pl.Float32, pl.Float64).fill_nan(None)).drop("_Volume_Limpo", "_Desvio_20")


def gerar_sinal(df: pl.DataFrame, empresa: str, ticker: str, perfil_risco: str = "Moderado", janela_dias: int | None = None) -> Signal:
    df_ind = calcular_indicadores_sinal(df).drop_nulls()
    if df_ind.height < 30:
        raise ValueError("Historico insuficiente para calcular um sinal confiavel.")

    atual = df_ind.row(-1, named=True)
    anterior = df_ind.row(-2, named=True)
    close = float(atual["Close"])
    atr = max(float(atual["ATR_14"]), close * 0.008)
    volume = float(atual["Volume"])
    volume_medio = float(atual["Volume_Medio_20"])

    pontos_compra = 0
    pontos_venda = 0
    gatilhos: list[str] = []

    if atual["MME_9"] > atual["MME_20"] > atual["MME_50"]:
        pontos_compra += 24
        gatilhos.append("tendencia curta compradora")
    elif atual["MME_9"] < atual["MME_20"] < atual["MME_50"]:
        pontos_venda += 24
        gatilhos.append("tendencia curta vendedora")

    if close > atual["VWAP"]:
        pontos_compra += 14
        gatilhos.append("preco acima do VWAP")
    elif close < atual["VWAP"]:
        pontos_venda += 14
        gatilhos.append("preco abaixo do VWAP")

    if atual["MACD_Hist"] > 0 and atual["MACD_Hist"] > anterior["MACD_Hist"]:
        pontos_compra += 18
        gatilhos.append("MACD acelerando")
    elif atual["MACD_Hist"] < 0 and atual["MACD_Hist"] < anterior["MACD_Hist"]:
        pontos_venda += 18
        gatilhos.append("MACD pressionando")

    if 45 <= atual["RSI_14"] <= 68:
        pontos_compra += 12
        gatilhos.append("RSI com espaco para alta")
    elif 32 <= atual["RSI_14"] <= 55:
        pontos_venda += 12
        gatilhos.append("RSI com espaco para queda")

    if atual["ADX_14"] >= 22:
        if atual["DI_Plus_14"] > atual["DI_Minus_14"]:
            pontos_compra += 12
            gatilhos.append("ADX confirma forca compradora")
        elif atual["DI_Minus_14"] > atual["DI_Plus_14"]:
            pontos_venda += 12
            gatilhos.append("ADX confirma forca vendedora")

    if anterior["Stoch_K"] <= anterior["Stoch_D"] and atual["Stoch_K"] > atual["Stoch_D"] and atual["Stoch_K"] < 80:
        pontos_compra += 8
        gatilhos.append("Estocastico cruzou para cima")
    elif anterior["Stoch_K"] >= anterior["Stoch_D"] and atual["Stoch_K"] < atual["Stoch_D"] and atual["Stoch_K"] > 20:
        pontos_venda += 8
        gatilhos.append("Estocastico cruzou para baixo")

    if 0.15 <= atual["BB_Posicao"] <= 0.45 and close > atual["VWAP"]:
        pontos_compra += 6
        gatilhos.append("preco reage na metade inferior de Bollinger")
    elif 0.55 <= atual["BB_Posicao"] <= 0.85 and close < atual["VWAP"]:
        pontos_venda += 6
        gatilhos.append("preco perde metade superior de Bollinger")

    if volume > volume_medio * 1.08:
        pontos_compra += 8
        pontos_venda += 8
        gatilhos.append("volume acima da media")

    stop_mult = {"Conservador": 1.0, "Moderado": 1.2, "Agressivo": 1.45}[perfil_risco]
    alvo_mult = {"Conservador": 1.45, "Moderado": 1.85, "Agressivo": 2.25}[perfil_risco]

    if pontos_compra - pontos_venda >= 16:
        direcao = "COMPRA"
        classe = "signal-buy"
        entrada = close
        stop = close - atr * stop_mult
        alvo = close + atr * alvo_mult
        confianca = min(94, 48 + pontos_compra - int(pontos_venda * 0.45))
    elif pontos_venda - pontos_compra >= 16:
        direcao = "VENDA"
        classe = "signal-sell"
        entrada = close
        stop = close + atr * stop_mult
        alvo = close - atr * alvo_mult
        confianca = min(94, 48 + pontos_venda - int(pontos_compra * 0.45))
    else:
        direcao = "AGUARDAR"
        classe = "signal-wait"
        entrada = close
        stop = None
        alvo = None
        confianca = max(35, 60 - abs(pontos_compra - pontos_venda))
        gatilhos.append("sem assimetria operacional suficiente")

    risco = abs(entrada - stop) if stop else None
    retorno = abs(alvo - entrada) if alvo else None

    return Signal(
        empresa=empresa,
        ticker=ticker,
        direcao=direcao,
        classe=classe,
        entrada=entrada,
        stop=stop,
        alvo=alvo,
        rr=retorno / risco if risco else None,
        confianca=int(confianca),
        rsi=float(atual["RSI_14"]),
        macd_hist=float(atual["MACD_Hist"]),
        atr=atr,
        adx=float(atual["ADX_14"]),
        stoch_k=float(atual["Stoch_K"]),
        bollinger_posicao=float(atual["BB_Posicao"]),
        volume_relativo=volume / volume_medio if volume_medio else 0,
        gatilhos=gatilhos[:5],
        janela_dias=janela_dias,
    )

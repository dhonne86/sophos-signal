from pathlib import Path

import matplotlib.pyplot as plt
import polars as pl


def calcular_supertrend(df: pl.DataFrame, multiplicador: float = 3.0) -> pl.DataFrame:
    hl2 = ((df["High"] + df["Low"]) / 2).to_list()
    atr = df["ATR_14"].to_list()
    close = df["Close"].to_list()

    banda_superior = [hl2[i] + multiplicador * atr[i] if atr[i] is not None else None for i in range(len(df))]
    banda_inferior = [hl2[i] - multiplicador * atr[i] if atr[i] is not None else None for i in range(len(df))]
    supertrend: list[float | None] = []
    direcao: list[int] = []

    for i in range(len(df)):
        if i == 0 or banda_inferior[i] is None or banda_superior[i] is None:
            supertrend.append(banda_inferior[i])
            direcao.append(1)
            continue

        prev_supertrend = supertrend[i - 1] if supertrend[i - 1] is not None else banda_inferior[i]
        prev_direcao = direcao[i - 1]

        if close[i] > prev_supertrend:
            direcao_atual = 1
        elif close[i] < prev_supertrend:
            direcao_atual = -1
        else:
            direcao_atual = prev_direcao

        if direcao_atual == 1:
            supertrend.append(max(banda_inferior[i], prev_supertrend))
        else:
            supertrend.append(min(banda_superior[i], prev_supertrend))
        direcao.append(direcao_atual)

    return df.with_columns(
        pl.Series("SuperTrend", supertrend),
        pl.Series("SuperTrend_Direcao", direcao),
    )


def gerar_indicadores_tecnicos():
    """
    Calcula indicadores tecnicos populares em plataformas como Nelogica e TradingView.
    Salva a serie completa em TecnicoOutput/indicadores.csv.
    """
    entrada = Path("LSTMOutput/dados.csv")
    if not entrada.exists():
        print("Erro: o arquivo LSTMOutput/dados.csv nao foi encontrado.")
        return

    df = pl.read_csv(entrada, try_parse_dates=True)
    if "Date" in df.columns:
        df = df.with_columns(pl.col("Date").cast(pl.Datetime, strict=False)).sort("Date")

    colunas_necessarias = {"Open", "High", "Low", "Close", "Volume"}
    if not colunas_necessarias.issubset(set(df.columns)):
        print("Erro: dados sem colunas OHLCV necessarias.")
        return

    close = pl.col("Close")
    high = pl.col("High")
    low = pl.col("Low")
    volume = pl.col("Volume")
    delta = close.diff()
    ganho = delta.clip(lower_bound=0)
    perda = -delta.clip(upper_bound=0)
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
        (100 - (100 / (1 + (media_ganho / media_perda.replace(0, None))))).alias("RSI_14"),
        (ema_12 - ema_26).alias("MACD"),
        close.ewm_mean(span=9, adjust=False).alias("MME_9"),
        close.ewm_mean(span=20, adjust=False).alias("MME_20"),
        close.ewm_mean(span=50, adjust=False).alias("MME_50"),
        close.ewm_mean(span=200, adjust=False).alias("MME_200"),
        close.rolling_mean(window_size=20).alias("SMA_20"),
        ((preco_tipico * volume).cum_sum() / volume.cum_sum()).alias("VWAP"),
        true_range.ewm_mean(alpha=1 / 14, adjust=False).alias("ATR_14"),
    )

    df = df.with_columns(
        pl.col("MACD").ewm_mean(span=9, adjust=False).alias("MACD_Signal"),
        pl.col("Close").rolling_std(window_size=20).alias("_Desvio_20"),
    )
    df = df.with_columns(
        (pl.col("MACD") - pl.col("MACD_Signal")).alias("MACD_Hist"),
        pl.col("SMA_20").alias("BB_Media"),
        (pl.col("SMA_20") + 2 * pl.col("_Desvio_20")).alias("BB_Superior"),
        (pl.col("SMA_20") - 2 * pl.col("_Desvio_20")).alias("BB_Inferior"),
    )
    df = df.with_columns(
        ((pl.col("BB_Superior") - pl.col("BB_Inferior")) / pl.col("BB_Media")).alias("BB_Largura"),
    )

    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = pl.when((up_move > down_move) & (up_move > 0)).then(up_move).otherwise(0)
    minus_dm = pl.when((down_move > up_move) & (down_move > 0)).then(down_move).otherwise(0)
    plus_di = 100 * plus_dm.ewm_mean(alpha=1 / 14, adjust=False) / pl.col("ATR_14")
    minus_di = 100 * minus_dm.ewm_mean(alpha=1 / 14, adjust=False) / pl.col("ATR_14")
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)

    menor_14 = low.rolling_min(window_size=14)
    maior_14 = high.rolling_max(window_size=14)
    stoch_k = 100 * (close - menor_14) / (maior_14 - menor_14)
    direcao_volume = pl.when(close.diff() > 0).then(1).when(close.diff() < 0).then(-1).otherwise(0)

    df = df.with_columns(
        plus_di.alias("DI_Plus_14"),
        minus_di.alias("DI_Minus_14"),
        dx.ewm_mean(alpha=1 / 14, adjust=False).alias("ADX_14"),
        stoch_k.alias("Stoch_K"),
        stoch_k.rolling_mean(window_size=3).alias("Stoch_D"),
        ((high.rolling_max(window_size=9) + low.rolling_min(window_size=9)) / 2).alias("Ichimoku_Tenkan"),
        ((high.rolling_max(window_size=26) + low.rolling_min(window_size=26)) / 2).alias("Ichimoku_Kijun"),
        ((direcao_volume * volume).fill_null(0).cum_sum()).alias("OBV"),
        ((high.shift(1) + low.shift(1) + close.shift(1)) / 3).alias("Pivot"),
    )
    df = df.with_columns(
        (((pl.col("Ichimoku_Tenkan") + pl.col("Ichimoku_Kijun")) / 2).shift(26)).alias("Ichimoku_Senkou_A"),
        (((high.rolling_max(window_size=52) + low.rolling_min(window_size=52)) / 2).shift(26)).alias("Ichimoku_Senkou_B"),
        (2 * pl.col("Pivot") - low.shift(1)).alias("Resistencia_1"),
        (2 * pl.col("Pivot") - high.shift(1)).alias("Suporte_1"),
    ).drop("_Desvio_20")

    df = calcular_supertrend(df)

    output_dir = Path("TecnicoOutput")
    output_dir.mkdir(parents=True, exist_ok=True)
    df.write_csv(output_dir / "indicadores.csv")

    print(f"Indicadores tecnicos salvos em: {output_dir / 'indicadores.csv'}")


def plotar_indicadores_tecnicos():
    """
    Gera um painel tecnico com medias, Bollinger, VWAP, SuperTrend,
    MACD, RSI, ADX, Estocastico, ATR e OBV.
    """
    caminho_csv = Path("TecnicoOutput/indicadores.csv")
    if not caminho_csv.exists():
        print("Erro: Arquivo de indicadores tecnicos nao encontrado.")
        return

    df = pl.read_csv(caminho_csv, try_parse_dates=True).sort("Date").to_pandas()
    df["Date"] = df["Date"].astype("datetime64[ns]")
    df.set_index("Date", inplace=True)

    fig, axes = plt.subplots(6, 1, figsize=(16, 20), sharex=True)

    axes[0].plot(df.index, df["Close"], label="Fechamento", color="#17231f", linewidth=1.4)
    axes[0].plot(df.index, df["MME_20"], label="MME 20", color="#0f766e", linewidth=1)
    axes[0].plot(df.index, df["MME_50"], label="MME 50", color="#2563eb", linewidth=1)
    axes[0].plot(df.index, df["MME_200"], label="MME 200", color="#7c3aed", linewidth=1)
    axes[0].plot(df.index, df["VWAP"], label="VWAP", color="#ea580c", linewidth=1)
    axes[0].plot(df.index, df["SuperTrend"], label="SuperTrend", color="#dc2626", linewidth=1)
    axes[0].plot(df.index, df["BB_Superior"], label="Bollinger Sup.", color="#94a3b8", linewidth=0.8)
    axes[0].plot(df.index, df["BB_Inferior"], label="Bollinger Inf.", color="#94a3b8", linewidth=0.8)
    axes[0].fill_between(
        df.index,
        df["BB_Inferior"].to_numpy(dtype=float),
        df["BB_Superior"].to_numpy(dtype=float),
        color="#94a3b8",
        alpha=0.12,
    )
    axes[0].set_title("Preco, Medias, VWAP, Bollinger e SuperTrend")
    axes[0].legend(loc="upper left", ncol=4, fontsize=8)

    axes[1].plot(df.index, df["MACD"], label="MACD", color="#2563eb")
    axes[1].plot(df.index, df["MACD_Signal"], label="Signal", color="#dc2626")
    axes[1].bar(df.index, df["MACD_Hist"], label="Histograma", color="#64748b", alpha=0.35)
    axes[1].axhline(0, color="#1f2937", linewidth=0.8)
    axes[1].set_title("MACD")
    axes[1].legend(loc="upper left", fontsize=8)

    axes[2].plot(df.index, df["RSI_14"], label="RSI 14", color="#7c3aed")
    axes[2].axhline(70, linestyle="--", color="#dc2626", alpha=0.7)
    axes[2].axhline(30, linestyle="--", color="#16a34a", alpha=0.7)
    axes[2].set_ylim(0, 100)
    axes[2].set_title("RSI")
    axes[2].legend(loc="upper left", fontsize=8)

    axes[3].plot(df.index, df["ADX_14"], label="ADX 14", color="#0f766e")
    axes[3].plot(df.index, df["DI_Plus_14"], label="DI+", color="#16a34a", alpha=0.8)
    axes[3].plot(df.index, df["DI_Minus_14"], label="DI-", color="#dc2626", alpha=0.8)
    axes[3].axhline(25, linestyle="--", color="#64748b", alpha=0.7)
    axes[3].set_title("ADX e Direcional")
    axes[3].legend(loc="upper left", fontsize=8)

    axes[4].plot(df.index, df["Stoch_K"], label="%K", color="#2563eb")
    axes[4].plot(df.index, df["Stoch_D"], label="%D", color="#ea580c")
    axes[4].axhline(80, linestyle="--", color="#dc2626", alpha=0.7)
    axes[4].axhline(20, linestyle="--", color="#16a34a", alpha=0.7)
    axes[4].set_ylim(0, 100)
    axes[4].set_title("Estocastico")
    axes[4].legend(loc="upper left", fontsize=8)

    axes[5].plot(df.index, df["ATR_14"], label="ATR 14", color="#0f766e")
    eixo_obv = axes[5].twinx()
    eixo_obv.plot(df.index, df["OBV"], label="OBV", color="#7c3aed", alpha=0.7)
    axes[5].set_title("ATR e OBV")
    axes[5].legend(loc="upper left", fontsize=8)
    eixo_obv.legend(loc="upper right", fontsize=8)

    for ax in axes:
        ax.grid(True, alpha=0.18)

    plt.tight_layout()
    saida = Path("TecnicoOutput/indicadores.png")
    plt.savefig(saida, dpi=140)
    plt.close()

    print(f"Grafico salvo em: {saida}")

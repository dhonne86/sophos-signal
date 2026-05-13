from datetime import date, datetime, timedelta
from dataclasses import asdict
import math
import os

import polars as pl
import streamlit as st

from signal_engine import gerar_sinal
from Util import (
    baixar_dados_b3,
    buscar_cotacao_brapi,
    carregar_config,
    limpar_pastas,
    obter_openai_api_key,
)

config = carregar_config()
JANELA_SINAL_DIAS = 90

st.set_page_config(
    page_title="Sophos Signal | Daytrade SaaS",
    page_icon="SP",
    layout="wide",
    initial_sidebar_state="expanded",
)


def aplicar_estilos():
    st.markdown(
        """
        <style>
        :root {
            --sophos-green: #0f766e;
            --sophos-blue: #2563eb;
            --sophos-red: #dc2626;
            --sophos-amber: #b45309;
            --sophos-ink: #17231f;
            --sophos-muted: #5b6b66;
            --sophos-line: #dbe5e1;
            --sophos-soft: #f4f8f6;
            --sophos-panel: #ffffff;
        }

        .block-container {
            padding-top: 1rem;
            padding-bottom: 2.5rem;
            max-width: 1280px;
        }

        h1, h2, h3 {
            color: var(--sophos-ink);
            letter-spacing: 0;
        }

        .sophos-hero {
            border: 1px solid var(--sophos-line);
            border-radius: 8px;
            padding: 1.1rem 1.25rem;
            background: #ffffff;
            margin-bottom: 1rem;
        }

        .sophos-brand {
            color: var(--sophos-green);
            font-size: 0.82rem;
            font-weight: 760;
            text-transform: uppercase;
            margin-bottom: 0.3rem;
        }

        .sophos-title {
            font-size: 2rem;
            line-height: 1.08;
            font-weight: 780;
            margin: 0;
        }

        .sophos-copy {
            color: var(--sophos-muted);
            font-size: 1rem;
            margin: 0.65rem 0 0;
            max-width: 860px;
        }

        .sophos-section-label {
            color: var(--sophos-muted);
            font-size: 0.8rem;
            font-weight: 740;
            text-transform: uppercase;
            margin-bottom: 0.35rem;
        }

        .signal-card {
            border: 1px solid var(--sophos-line);
            border-radius: 8px;
            padding: 1rem;
            background: var(--sophos-panel);
            min-height: 166px;
        }

        .signal-buy {
            border-left: 5px solid var(--sophos-green);
        }

        .signal-sell {
            border-left: 5px solid var(--sophos-red);
        }

        .signal-wait {
            border-left: 5px solid var(--sophos-amber);
        }

        .signal-kicker {
            color: var(--sophos-muted);
            font-size: 0.78rem;
            font-weight: 740;
            text-transform: uppercase;
            margin-bottom: 0.35rem;
        }

        .signal-title {
            font-size: 1.35rem;
            font-weight: 780;
            margin-bottom: 0.3rem;
        }

        .signal-meta {
            color: var(--sophos-muted);
            font-size: 0.92rem;
            line-height: 1.45;
        }

        .mini-pill {
            display: inline-block;
            border: 1px solid var(--sophos-line);
            border-radius: 999px;
            padding: 0.22rem 0.55rem;
            margin: 0.15rem 0.2rem 0.15rem 0;
            color: var(--sophos-ink);
            background: var(--sophos-soft);
            font-size: 0.82rem;
            font-weight: 650;
        }

        div[data-testid="stMetric"] {
            border: 1px solid var(--sophos-line);
            border-radius: 8px;
            padding: 0.8rem 0.9rem;
            background: #ffffff;
        }

        div[data-testid="stMetricLabel"] {
            color: var(--sophos-muted);
        }

        section[data-testid="stSidebar"] {
            background: var(--sophos-soft);
            border-right: 1px solid var(--sophos-line);
        }

        .stButton > button {
            width: 100%;
            border-radius: 8px;
            border: 1px solid var(--sophos-green);
            background: var(--sophos-green);
            color: #ffffff;
            font-weight: 720;
        }

        .stButton > button:hover {
            border-color: #115e59;
            background: #115e59;
            color: #ffffff;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def inicializar_estado():
    st.session_state.setdefault("plano", "Starter")
    st.session_state.setdefault("creditos_usados", 7)
    st.session_state.setdefault("limite_creditos", 30)
    st.session_state.setdefault("historico_sinais", [])
    st.session_state.setdefault("watchlist", ["PETR4.SA", "VALE3.SA", "ITUB4.SA", "BBDC4.SA"])


def formatar_brl(valor):
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return "-"
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_numero(valor):
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return "-"
    return f"{valor:,.0f}".replace(",", ".")


def formatar_pct(valor):
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return "-"
    return f"{valor:.2f}%".replace(".", ",")


def salvar_upload(uploaded_file, caminho: str):
    if uploaded_file:
        os.makedirs(os.path.dirname(caminho), exist_ok=True)
        with open(caminho, "wb") as f:
            f.write(uploaded_file.read())
        st.sidebar.success("Arquivo fundamentalista salvo.")


def renderizar_hero():
    st.markdown(
        """
        <div class="sophos-hero">
            <div class="sophos-brand">Sophos Signal</div>
            <h1 class="sophos-title">MVP SaaS para sinais de daytrade</h1>
            <p class="sophos-copy">
                Radar operacional para ativos da B3 com setup, entrada, stop,
                alvo, score de confianca, historico e camada opcional de research com IA.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def renderizar_cotacao(ticker_yahoo: str):
    st.markdown('<div class="sophos-section-label">Mercado agora</div>', unsafe_allow_html=True)
    cotacao = buscar_cotacao_brapi(ticker_yahoo)
    if cotacao.get("erro"):
        st.warning(cotacao["erro"])
        return

    preco = cotacao.get("regularMarketPrice")
    variacao = cotacao.get("regularMarketChange")
    variacao_pct = cotacao.get("regularMarketChangePercent")
    volume = cotacao.get("regularMarketVolume")
    maxima = cotacao.get("regularMarketDayHigh")
    minima = cotacao.get("regularMarketDayLow")
    horario = cotacao.get("regularMarketTime")

    col_preco, col_var, col_volume, col_faixa = st.columns(4)
    col_preco.metric("Preco atual", formatar_brl(preco))
    col_var.metric(
        "Variacao do dia",
        formatar_pct(variacao_pct),
        formatar_brl(variacao) if variacao is not None else None,
    )
    col_volume.metric("Volume", formatar_numero(volume))
    col_faixa.metric(
        "Min / Max",
        f"{formatar_brl(minima)} / {formatar_brl(maxima)}"
        if minima is not None and maxima is not None
        else "-",
    )
    if horario:
        st.caption(f"Fonte: BRAPI | Ultima atualizacao: {horario}")


@st.cache_data(ttl=900, show_spinner=False)
def carregar_dados_sinal(ticker_yahoo: str, data_inicio: date, data_fim: date) -> pl.DataFrame:
    return baixar_dados_b3(ticker=ticker_yahoo, inicio=str(data_inicio), fim=str(data_fim))


def buscar_sinal_rapido(empresa_nome: str, ticker_yahoo: str, janela_dias: int, perfil_risco: str):
    data_fim = date.today()
    data_inicio = data_fim - timedelta(days=janela_dias)
    df = carregar_dados_sinal(ticker_yahoo, data_inicio, data_fim)
    if df.is_empty():
        raise ValueError("Nao foi possivel baixar dados historicos para o ticker selecionado.")
    sinal = asdict(gerar_sinal(df, empresa_nome, ticker_yahoo, perfil_risco, janela_dias=janela_dias))
    sinal["hora"] = datetime.now().strftime("%d/%m/%Y %H:%M")
    sinal["validade"] = "proximo pregao / 60-120 min apos abertura"
    st.session_state["historico_sinais"].insert(0, sinal)
    st.session_state["creditos_usados"] += 1
    return sinal


def renderizar_card_sinal(sinal: dict):
    gatilhos_html = "".join([f'<span class="mini-pill">{item}</span>' for item in sinal["gatilhos"]])
    stop = formatar_brl(sinal["stop"]) if sinal["stop"] else "-"
    alvo = formatar_brl(sinal["alvo"]) if sinal["alvo"] else "-"
    rr = f"{sinal['rr']:.2f}" if sinal["rr"] else "-"
    st.markdown(
        f"""
        <div class="signal-card {sinal['classe']}">
            <div class="signal-kicker">{sinal['ticker']} | {sinal['hora']}</div>
            <div class="signal-title">{sinal['direcao']} - {sinal['empresa']}</div>
            <div class="signal-meta">
                Entrada: <b>{formatar_brl(sinal['entrada'])}</b> |
                Stop: <b>{stop}</b> |
                Alvo: <b>{alvo}</b> |
                R/R: <b>{rr}</b><br>
                Confianca: <b>{sinal['confianca']}%</b> |
                RSI: <b>{sinal['rsi']:.1f}</b> |
                Vol. relativo: <b>{sinal['volume_relativo']:.2f}x</b><br>
                Validade: {sinal['validade']}
            </div>
            <div style="margin-top:0.65rem;">{gatilhos_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def renderizar_saas_home(empresa_nome, ticker_yahoo, janela_dias, perfil_risco):
    usados = st.session_state["creditos_usados"]
    limite = st.session_state["limite_creditos"]
    plano = st.session_state["plano"]
    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric("Plano", plano)
    col_b.metric("Sinais usados", f"{usados}/{limite}")
    col_c.metric("Watchlist", len(st.session_state["watchlist"]))
    col_d.metric("Janela tecnica", f"{janela_dias} dias")

    st.divider()
    aba_radar, aba_sinal, aba_historico, aba_planos = st.tabs(
        ["Radar", "Sinal ao vivo", "Historico", "Assinatura"]
    )

    with aba_radar:
        st.markdown("### Radar operacional")
        cols = st.columns(4)
        universo = st.session_state["watchlist"][:4]
        for idx, ativo in enumerate(universo):
            papel = ativo.replace(".SA", "")
            with cols[idx]:
                st.markdown(
                    f"""
                    <div class="signal-card">
                        <div class="signal-kicker">Monitorado</div>
                        <div class="signal-title">{papel}</div>
                        <div class="signal-meta">
                            Alertas: tendencia, VWAP, MACD e volume.<br>
                            Plano atual: {plano}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        st.info(
            "MVP: os sinais sao educacionais e devem ser validados pelo trader. "
            f"O radar usa os ultimos {janela_dias} dias para manter a resposta rapida. "
            "Para producao, conecte dados intraday de corretora ou market data pago."
        )

    with aba_sinal:
        st.markdown("### Gerar sinal")
        renderizar_cotacao(ticker_yahoo)
        gerar = st.button("Gerar sinal do ativo selecionado", type="primary")
        if gerar:
            if usados >= limite:
                st.error("Limite do plano atingido. Faca upgrade para continuar.")
            else:
                with st.spinner("Calculando setup, risco e score..."):
                    try:
                        sinal = buscar_sinal_rapido(
                            empresa_nome,
                            ticker_yahoo,
                            janela_dias,
                            perfil_risco,
                        )
                    except Exception as exc:
                        st.error(str(exc))
                    else:
                        renderizar_card_sinal(sinal)
        elif st.session_state["historico_sinais"]:
            st.caption("Ultimo sinal gerado nesta sessao")
            renderizar_card_sinal(st.session_state["historico_sinais"][0])

    with aba_historico:
        st.markdown("### Historico de sinais")
        if not st.session_state["historico_sinais"]:
            st.info("Nenhum sinal gerado ainda nesta sessao.")
        else:
            tabela = pl.DataFrame(st.session_state["historico_sinais"]).select(
                ["hora", "ticker", "empresa", "direcao", "entrada", "stop", "alvo", "rr", "confianca"]
            )
            st.dataframe(tabela, use_container_width=True, hide_index=True)

    with aba_planos:
        st.markdown("### Planos do MVP")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.subheader("Starter")
            st.write("30 sinais/mes, 1 watchlist, historico local.")
            st.metric("Preco sugerido", "R$ 49/m")
        with col2:
            st.subheader("Pro")
            st.write("300 sinais/mes, alertas WhatsApp, filtros por setup.")
            st.metric("Preco sugerido", "R$ 149/m")
        with col3:
            st.subheader("Mesa")
            st.write("Multiusuarios, ranking de setups, API e auditoria.")
            st.metric("Preco sugerido", "R$ 499/m")


def executar_pipeline(empresa_nome, ticker_yahoo, data_inicio, data_fim, dias_previsao, uploaded_excel_path):
    from AgentesAvaliadores import avaliador_1, avaliador_2
    from AgentesIndependentes import (
        analisar_fundamentalista,
        analisar_noticias,
        analisar_previsao,
        analisar_tecnico,
    )
    from LSTM import prever_com_lstm
    from Noticias import buscar_noticias_financeiras_ddg
    from Tecnico import gerar_indicadores_tecnicos, plotar_indicadores_tecnicos

    if not obter_openai_api_key():
        st.error(
            "Configure a variavel OPENAI_API_KEY antes de executar a analise. "
            "Em deploy, cadastre essa chave nos Secrets do provedor."
        )
        st.stop()

    limpar_pastas()

    with st.status("Executando analise completa", expanded=True) as status:
        st.write("Baixando dados historicos...")
        df = baixar_dados_b3(
            ticker=ticker_yahoo,
            inicio=str(data_inicio),
            fim=str(data_fim),
        )
        if df.is_empty():
            st.error("Nao foi possivel baixar dados para o ticker selecionado no periodo informado.")
            st.stop()

        st.write("Gerando previsao LSTM...")
        prever_com_lstm(df, ticker_yahoo, dias_previsao=dias_previsao)

        st.write("Buscando noticias...")
        buscar_noticias_financeiras_ddg(empresa_nome)

        st.write("Gerando indicadores tecnicos...")
        gerar_indicadores_tecnicos()
        plotar_indicadores_tecnicos()

        st.write("Executando agentes independentes...")
        ind_previsao = analisar_previsao()
        ind_tecnico = analisar_tecnico()
        ind_noticias = analisar_noticias()

        if os.path.exists(uploaded_excel_path):
            ind_fundamentalista = analisar_fundamentalista("entrada_fundamentalista.xlsx")
        else:
            ind_fundamentalista = (
                "Analise fundamentalista nao executada: envie um arquivo Excel "
                "antes de executar a analise."
            )

        st.write("Executando avaliadores finais...")
        pareceres = [ind_previsao, ind_tecnico, ind_noticias, ind_fundamentalista]
        avalia_1 = avaliador_1(pareceres)
        avalia_2 = avaliador_2(pareceres)
        status.update(label="Analise concluida", state="complete")

    return {
        "ind_previsao": ind_previsao,
        "ind_tecnico": ind_tecnico,
        "ind_noticias": ind_noticias,
        "ind_fundamentalista": ind_fundamentalista,
        "avalia_1": avalia_1,
        "avalia_2": avalia_2,
    }


def renderizar_resultados(resultados):
    st.success("Analise concluida.")
    aba1, aba2, aba3, aba4, aba5, aba6, aba7, aba8, aba9 = st.tabs(
        [
            "LSTM",
            "Noticias",
            "Tecnicos",
            "Fundamentalista",
            "Previsao",
            "Tecnica",
            "Sentimento",
            "Avaliador 1",
            "Avaliador 2",
        ]
    )

    with aba1:
        st.image("LSTMOutput/previsao.png", caption="Previsao com LSTM", use_container_width=True)

    with aba2:
        try:
            with open("NoticiasOutput/noticias.txt", "r", encoding="utf-8") as f:
                noticias_texto = f.read()
            st.text_area("Noticias Financeiras", noticias_texto, height=420)
        except FileNotFoundError:
            st.warning("Arquivo de noticias nao encontrado.")

    with aba3:
        st.image(
            "TecnicoOutput/indicadores.png",
            caption="Indicadores Tecnicos",
            use_container_width=True,
        )

    with aba4:
        st.markdown(f"### Analise Fundamentalista\n{resultados['ind_fundamentalista']}")

    with aba5:
        st.markdown(f"### Analise de Previsao\n{resultados['ind_previsao']}")

    with aba6:
        st.markdown(f"### Analise Tecnica\n{resultados['ind_tecnico']}")

    with aba7:
        st.markdown(f"### Analise de Sentimento\n{resultados['ind_noticias']}")

    with aba8:
        st.markdown(f"### Avaliador 1\n{resultados['avalia_1']}")

    with aba9:
        st.markdown(f"### Avaliador 2\n{resultados['avalia_2']}")


aplicar_estilos()
inicializar_estado()
renderizar_hero()

tickers_df = pl.read_csv("Diversos/ticker.csv")
ticker_dict = dict(zip(tickers_df["Nome"].to_list(), tickers_df["YahooTicker"].to_list()))

with st.sidebar:
    st.title("Sophos Signal")
    st.caption("MVP SaaS")
    modo = st.radio("Modulo", ["Sinais daytrade", "Research IA"], horizontal=False)

    st.divider()
    empresa_nome = st.selectbox("Empresa", options=list(ticker_dict.keys()))
    ticker_yahoo = ticker_dict[empresa_nome]

    st.divider()
    perfil_risco = st.segmented_control(
        "Perfil de risco",
        ["Conservador", "Moderado", "Agressivo"],
        default="Moderado",
    )
    janela_sinal_dias = st.number_input(
        "Janela dos sinais",
        min_value=60,
        max_value=180,
        value=JANELA_SINAL_DIAS,
        step=15,
        help="Periodo complementar usado no radar rapido. O padrao de 90 dias melhora a performance.",
    )
    st.caption(
        f"Sinais usam {janela_sinal_dias} dias ate {date.today().strftime('%d/%m/%Y')}. "
        "O periodo longo fica no Research IA."
    )

    st.divider()
    watchlist_texto = st.text_area(
        "Watchlist SaaS",
        value="\n".join(st.session_state["watchlist"]),
        height=118,
    )
    st.session_state["watchlist"] = [
        item.strip().upper()
        for item in watchlist_texto.splitlines()
        if item.strip()
    ][:12]

    st.divider()
    st.session_state["plano"] = st.selectbox("Plano simulado", ["Starter", "Pro", "Mesa"], index=0)
    limites = {"Starter": 30, "Pro": 300, "Mesa": 3000}
    st.session_state["limite_creditos"] = limites[st.session_state["plano"]]

    if modo == "Research IA":
        st.divider()
        data_inicio = st.date_input("Data de inicio do research", value=date(2024, 1, 1))
        data_fim = st.date_input("Data de fim do research", value=date.today())
        dias_previsao = st.slider(
            "Dias futuros com LSTM",
            min_value=30,
            max_value=180,
            value=126,
            step=1,
        )
        uploaded_excel_path = "DocsAnaliseFund/entrada_fundamentalista.xlsx"
        uploaded_files = st.file_uploader(
            "Planilha fundamentalista",
            type=["xlsx"],
            accept_multiple_files=False,
        )
        salvar_upload(uploaded_files, uploaded_excel_path)

        st.divider()
        openai_status = "Configurada" if obter_openai_api_key() else "Pendente"
        st.caption(f"OpenAI: {openai_status}")
        executar = st.button("Executar research", type="primary")
    else:
        data_inicio = date.today() - timedelta(days=int(janela_sinal_dias))
        data_fim = date.today()
        dias_previsao = 126
        uploaded_excel_path = "DocsAnaliseFund/entrada_fundamentalista.xlsx"
        executar = False

st.markdown(f"### {empresa_nome}")
st.caption(f"Ticker de referencia: `{ticker_yahoo}`")

if modo == "Sinais daytrade":
    renderizar_saas_home(empresa_nome, ticker_yahoo, int(janela_sinal_dias), perfil_risco)
else:
    renderizar_cotacao(ticker_yahoo)
    st.divider()
    st.markdown("### Research multiagentes")
    st.write(
        "Use os parametros na lateral para executar o pipeline completo. "
        "Os resultados serao exibidos em abas com graficos, noticias e pareceres."
    )
    st.info(
        "Este modulo usa OpenAI, noticias, LSTM e indicadores tecnicos. "
        "Ele complementa os sinais do MVP com uma analise mais profunda."
    )

    if executar:
        resultados = executar_pipeline(
            empresa_nome=empresa_nome,
            ticker_yahoo=ticker_yahoo,
            data_inicio=data_inicio,
            data_fim=data_fim,
            dias_previsao=dias_previsao,
            uploaded_excel_path=uploaded_excel_path,
        )
        renderizar_resultados(resultados)

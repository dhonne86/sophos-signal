# Sophos Signal

MVP SaaS em Streamlit para sinais educacionais de daytrade na B3, com radar tecnico, entrada, stop, alvo, score de confianca, historico da sessao e envio diario por e-mail. O modulo de research com LSTM, noticias e agentes OpenAI segue disponivel como camada complementar.

## Recursos

- MVP de sinais com janela tecnica padrao dos ultimos 90 dias
- Processamento de CSVs, indicadores e sinais com Polars
- Setup operacional com direcao, entrada, stop, alvo e risco/retorno
- Watchlist, planos simulados e historico de sinais
- Pagina HTML diaria gerada por `daily_signal_email.py`
- Envio diario por SMTP para `dhonne137@gmail.com` quando o `.env` estiver configurado
- Selecao de empresas a partir de `Diversos/ticker.csv`
- Cotacao atual da B3 via BRAPI
- Download de dados historicos via Yahoo Finance
- Previsao de precos com LSTM
- Indicadores tecnicos: RSI, MACD e medias moveis
- Busca de noticias financeiras com tolerancia a rate limit
- Canais nacionais e internacionais para IBOVESPA, B3 e cenarios macroeconomicos
- Analise por agentes independentes e avaliadores finais
- Upload opcional de planilha Excel para analise fundamentalista

## Execucao local

1. Crie e ative um ambiente virtual:

```powershell
python -m venv venv
.\venv\Scripts\activate
```

2. Instale as dependencias:

```powershell
pip install -r requirements.txt
```

3. Configure as chaves:

```powershell
Copy-Item .env.example .env
```

Edite `.env` e preencha:

```env
OPENAI_API_KEY=sua_chave
BRAPI_API_KEY=sua_chave_brapi
```

Para envio de e-mail, configure tambem as variaveis SMTP na secao abaixo.

4. Execute:

```powershell
streamlit run app.py
```

O app ficara disponivel em `http://localhost:8501`.

## Envio diario por e-mail

O projeto inclui o script `daily_signal_email.py`, que gera `daily_signal_page.html`
com o sinal operacional dos ultimos 90 dias e envia o HTML para o e-mail configurado.

Configure no `.env`:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=seu_email@gmail.com
SMTP_PASSWORD=sua_senha_de_app
SMTP_FROM=seu_email@gmail.com
SIGNAL_EMAIL_TO=dhonne137@gmail.com
SIGNAL_TICKER=PETR4.SA
SIGNAL_EMPRESA=PETROBRAS
SIGNAL_WINDOW_DAYS=90
```

Teste sem enviar:

```powershell
.\venv\Scripts\python.exe daily_signal_email.py --dry-run
```

Envie manualmente:

```powershell
.\venv\Scripts\python.exe daily_signal_email.py --recipient dhonne137@gmail.com
```

## Deploy no Streamlit Community Cloud

1. Envie este projeto para um repositorio GitHub.
2. No Streamlit Community Cloud, crie um novo app apontando para `app.py`.
3. Em `Settings > Secrets`, adicione:

```toml
OPENAI_API_KEY = "sua_chave"
BRAPI_API_KEY = "sua_chave_brapi"
```

4. Confirme que `requirements.txt`, `config.yaml`, `Diversos/ticker.csv` e os arquivos `.py` estao no repositorio.

## Observacoes

- Nao versionar `.env` nem `.streamlit/secrets.toml`.
- A cotacao atual usa a BRAPI. O token deve ficar em `BRAPI_API_KEY`, nunca direto no codigo.
- A busca de noticias pode retornar rate limit do DuckDuckGo; nesse caso, o app continua a analise e registra o aviso em `NoticiasOutput/noticias.txt`.
- TensorFlow pode deixar o deploy mais pesado. Se o provedor tiver pouca memoria, reduza epocas/camadas do modelo LSTM ou use um modelo salvo.

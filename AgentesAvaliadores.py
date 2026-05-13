from Util import config, chamar_textual

def avaliador_1(pareceres: list[str]) -> str:
    prompt = config["prompts"]["avaliadores"]["avaliador_1"]
    texto = "\n\n".join(pareceres)
    model = config["modelos"]["avaliadores"]["avaliador_1"]
    return chamar_textual(prompt, texto, model)

def avaliador_2(pareceres: list[str]) -> str:
    prompt = config["prompts"]["avaliadores"]["avaliador_2"]
    texto = "\n\n".join(pareceres)
    model = config["modelos"]["avaliadores"]["avaliador_2"]
    return chamar_textual(prompt, texto,model)


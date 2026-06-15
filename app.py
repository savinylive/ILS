import serial, threading, time, os, json
from datetime import datetime
from flask import Flask, render_template, request, jsonify
app = Flask(__name__, template_folder='.')
PORTA_SERIAL, VELOCIDADE = 'COM3', 115200
TABELA_PILOTOS = {1:{"nome":"Piloto 1","numero":"17"}, 2:{"nome":"Piloto 2","numero":"44"}, 3:{"nome":"Piloto 3","numero":"05"}, 4:{"nome":"Piloto 4","numero":"99"}}
historico_passagens, ranking_atual_salvo, grid_final_salvo = {}, [], []
status_prova, tipo_sessao, relogio_inicial_texto = "AGUARDANDO", "TREINO", "00:00"
tempo_limite_prova, tempo_inicio_prova, parametro_prova = 0, 0, 5
vencedor_detectado = False
def formatar_tempo(milis):
	return f"{int(milis//60000):02d}:{int((milis%60000)//1000):02d}.{int(milis%1000):03d}"
def atualizar_relogio_loop():
	global status_prova, relogio_inicial_texto, tempo_limite_prova, tempo_inicio_prova
	while True:
		time.sleep(1)
		if status_prova in ["TREINO", "CLASSIFICACAO"]:
			tempo_restante = max(0, tempo_limite_prova - (time.time() - tempo_inicio_prova))
			relogio_inicial_texto = f"{int(tempo_restante // 60):02d}:{int(tempo_restante % 60):02d}"
			if tempo_restante <= 0: status_prova, relogio_inicial_texto = "BANDEIRADA", "00:00"
def processar_dados_serial():
	global status_prova, vencedor_detectado, relogio_inicial_texto, parametro_prova, historico_passagens
	try:
		ser = serial.Serial(PORTA_SERIAL, VELOCIDADE, timeout=1)
		time.sleep(2)
		while True:
			linha = ser.readline().decode('utf-8', errors='ignore').strip()
			if linha.startswith("KART:") and status_prova in ["TREINO", "CLASSIFICACAO", "CORRIDA", "BANDEIRADA"]:
				id_kart = int(linha.replace("KART:", "").split(","))
				tempo_atual_boxes = int(time.time() * 1000)
				if id_kart not in historico_passagens: historico_passagens[id_kart] = []
				historico_passagens[id_kart].append(tempo_atual_boxes)
				if status_prova == "CORRIDA" and (len(historico_passagens[id_kart]) - 1) >= parametro_prova and not vencedor_detectado: status_prova, vencedor_detectado, relogio_inicial_texto = "BANDEIRADA", True, "FIM"
	except: pass
def obter_ranking():
	global tipo_sessao, parametro_prova, relogio_inicial_texto, status_prova, grid_final_salvo
	if status_prova == "GRID_DEFINIDO": return grid_final_salvo
	ranking = []
	for id_kart in historico_passagens:
		if len(historico_passagens[id_kart]) >= 2:
			voltas_milis = [historico_passagens[id_kart][i] - historico_passagens[id_kart][i-1] for i in range(1, len(historico_passagens[id_kart]))]
			info = TABELA_PILOTOS.get(id_kart, {"nome": f"Kart {id_kart}", "numero": "??"})
			ranking.append({"id": id_kart, "piloto": info["nome"], "numero": info["numero"], "ultima": formatar_tempo(voltas_milis[-1]), "melhor": formatar_tempo(min(voltas_milis)), "melhor_bruto": min(voltas_milis), "voltas": len(voltas_milis), "ultimo_timestamp": historico_passagens[id_kart][-1]})
	ranking_ordenado = sorted(ranking, key=lambda x: x["melhor_bruto"]) if tipo_sessao in ["TREINO", "CLASSIFICACAO"] else sorted(ranking, key=lambda x: (-x["voltas"], x["ultimo_timestamp"]))
	if tipo_sessao == "CORRIDA" and ranking_ordenado and status_prova == "CORRIDA": relogio_inicial_texto = f"V. {ranking_ordenado[0]['voltas']}/{parametro_prova}"
	return ranking_ordenado
@app.route('/')
def index():
	return render_template('index.html')
@app.route('/dados')
def dados():
	global status_prova, relogio_inicial_texto
	return jsonify({"status": status_prova, "relogio": relogio_inicial_texto, "ranking": obter_ranking()})
@app.route('/cmd')
def cmd():
	global status_prova, tempo_limite_prova, tempo_inicio_prova, historico_passagens, relogio_inicial_texto, tipo_sessao, parametro_prova, vencedor_detectado, grid_final_salvo
	acao = request.args.get('acao')
	if acao == 'iniciar' and status_prova in ["AGUARDANDO", "GRID_DEFINIDO"]:
		parametro_prova, tipo_sessao, vencedor_detectado = int(request.args.get('valor', 5)), request.args.get('sessao', 'TREINO'), False
		historico_passagens.clear()
		if tipo_sessao in ["TREINO", "CLASSIFICACAO"]: tempo_limite_prova, tempo_inicio_prova, relogio_inicial_texto = parametro_prova * 60, time.time(), f"{parametro_prova:02d}:00"
		if tipo_sessao == "CORRIDA": relogio_inicial_texto = f"V. 0/{parametro_prova}"
		status_prova = tipo_sessao
	if acao == 'finalizar' and status_prova in ["TREINO", "CLASSIFICACAO", "CORRIDA", "BANDEIRADA"]:
		if tipo_sessao == "CLASSIFICACAO":
			grid_final_salvo = obter_ranking()
			status_prova, relogio_inicial_texto = "GRID_DEFINIDO", "GRID"
		else: status_prova, relogio_inicial_texto = "FINALIZADO", "FIM"
		agora = datetime.now()
		nome_pasta = f"SESSAO_{tipo_sessao}_{agora.strftime('%d_%m_%Y_%Hh%Mmin')}"
		if not os.path.exists(nome_pasta): os.makedirs(nome_pasta)
		with open(os.path.join(nome_pasta, "00_POSICOES.txt"), "w") as f:
			for idx, k in enumerate(obter_ranking()): f.write(f"{idx+1}o - Kart #{k['numero']} - {k['piloto']} - Melh: {k['melhor']}\n")
	if acao == 'resetar': historico_passagens.clear(); status_prova, relogio_inicial_texto = "AGUARDANDO", "--:--"
	return "ok"
@app.route('/cad')
def cad():
	global TABELA_PILOTOS
	TABELA_PILOTOS[int(request.args.get('id'))] = {"nome": request.args.get('nome'), "numero": request.args.get('numero')}
	return "ok"
@app.route('/falso')
def falso():
	global historico_passagens, status_prova
	id_kart = int(request.args.get('id', 1))
	if status_prova in ["TREINO", "CLASSIFICACAO", "CORRIDA", "BANDEIRADA"]:
		if id_kart not in historico_passagens: historico_passagens[id_kart] = []
		historico_passagens[id_kart].append(int(time.time() * 1000))
	return "ok"
if __name__ == '__main__':
	threading.Thread(target=processar_dados_serial, daemon=True).start()
	threading.Thread(target=atualizar_relogio_loop, daemon=True).start()
	app.run(host='0.0.0.0', port=5000, debug=False)

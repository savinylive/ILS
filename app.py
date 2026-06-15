import serial, threading, time, os, json
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify
app = Flask(__name__)
PORTA_SERIAL, VELOCIDADE = 'COM3', 115200
TABELA_PILOTOS = {1:{"nome":"Piloto 1","numero":"17"}, 2:{"nome":"Piloto 2","numero":"44"}, 3:{"nome":"Piloto 3","numero":"05"}, 4:{"nome":"Piloto 4","numero":"99"}}
historico_passagens, ranking_atual_salvo, grid_final_salvo = {}, [], []
status_prova, tipo_sessao, relogio_inicial_texto = "AGUARDANDO", "TREINO", "00:00"
tempo_limite_prova, tempo_inicio_prova, parametro_prova = 0, 0, 5
vencedor_detectado = False
HTML_PAINEL = """<!DOCTYPE html><html><head><title>ILS Timing</title>
<style>body{background:#0b0c10;color:#fff;font-family:sans-serif;text-align:center;margin:0}header{background:#1f2833;padding:15px;border-bottom:4px solid #ff4500;display:flex;justify-content:space-between;align-items:center;padding:10px 40px}.box{background:#151a21;padding:15px;border-radius:6px;border:1px solid #ff4500;display:flex;gap:12px;align-items:center;justify-content:center}table{width:95%;max-width:1200px;margin:20px auto;border-collapse:collapse;background:#1f2833}th,td{padding:12px;text-align:center;font-size:18px;border-bottom:1px solid #2c3540}th{background:#151a21;color:#ff4500}.numero-kart{background:#ff4500;color:#fff;padding:4px 10px;border-radius:4px;font-weight:bold}input,select,button{background:#1f2833;border:1px solid #ff4500;color:#fff;padding:8px;border-radius:4px;font-weight:bold}button{cursor:pointer;background:#ff4500}</style></head><body>
<header><h1><span style="color:#ff4500">ILS</span> TIMING</h1><div id="cronometro" style="font-size:32px;font-family:monospace;color:#ff4500">--:--</div><div id="status-label" style="font-weight:bold;padding:5px 15px;border-radius:4px;background:#2c3540">PISTA FECHADA</div></header>
<div style="display:flex;gap:20px;justify-content:center;margin-top:20px"><div class="box"><span>MODO:</span><select id="tipo-sessao" onchange="document.getElementById('lbl').innerText=this.value=='CORRIDA'?'VOLTAS':'MINUTOS'"><option value="TREINO">TREINO</option><option value="CLASSIFICACAO">CLASSIFICAÇÃO</option><option value="CORRIDA">CORRIDA</option></select><input type="number" id="p-prova" value="5" style="width:50px;text-align:center"><span id="lbl">MINUTOS</span><button onclick="fetch('/cmd?acao=iniciar&valor='+document.getElementById('p-prova').value+'&sessao='+document.getElementById('tipo-sessao').value)" style="background:#00ff00;color:#000">ABRIR</button><button onclick="if(confirm('Encerrar?'))fetch('/cmd?acao=finalizar')" style="background:#ff4500;color:#fff">FIM</button><button onclick="if(confirm('Resetar?'))fetch('/cmd?acao=resetar')" style="background:#ff0000;color:#fff">RESET</button></div>
<div class="box" style="border-color:#66fcf1"><span>CADASTRO:</span><input type="number" id="c-id" placeholder="ID" style="width:50px"><input type="text" id="c-nome" placeholder="Piloto" style="width:100px"><input type="text" id="c-num" placeholder="Kart" style="width:50px"><button onclick="fetch('/cad?id='+document.getElementById('c-id').value+'&nome='+document.getElementById('c-nome').value+'&numero='+document.getElementById('c-num').value);alert('Salvo!');" style="background:#66fcf1;color:#000">SALVAR</button></div></div>
<table><thead><tr><th>P.</th><th>Nº</th><th style="text-align:left">Piloto</th><th>Última Volta</th><th>Melhor Volta</th><th>Voltas</th></tr></thead><tbody id="tabela-tempos"><tr><td colspan="6" style="color:#888">Aguardando início...</td></tr></tbody></table>
<script>
setInterval(function(){fetch('/dados').then(r=>r.json()).then(d=>{
document.getElementById('cronometro').innerText=d.relogio;document.getElementById('status-label').innerText=d.status;const t=document.getElementById('tabela-tempos');if(d.ranking.length===0){t.innerHTML='<tr><td colspan="6">Pista aberta. Aguardando passagens...</td></tr>';return}
t.innerHTML='';d.ranking.forEach((k,idx)=>{t.innerHTML+=`<tr><td><b>${idx+1}º</b></td><td><span class="numero-kart">${k.numero}</span></td><td style="text-align:left">${k.piloto}</td><td>${k.ultima}</td><td style="color:#00ff00;font-weight:bold">${k.melhor}</td><td>${k.voltas}</td></tr>`})})},500);
</script></body></html>"""
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
				dados = linha.replace("KART:", "").split(",")
				id_kart = int(dados[0])
				tempo_atual_boxes = int(dados[1])
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
	return render_template_string(HTML_PAINEL)
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
	global historico_passagens, status_prova, vencedor_detectado, parametro_prova, relogio_inicial_texto
	id_kart = int(request.args.get('id', 1))
	tempo_recebido = int(request.args.get('tempo', int(time.time() * 1000)))
	if status_prova in ["TREINO", "CLASSIFICACAO", "CORRIDA", "BANDEIRADA"]:
		if id_kart not in historico_passagens: historico_passagens[id_kart] = []
		historico_passagens[id_kart].append(tempo_recebido)
		total_voltas = len(historico_passagens[id_kart]) - 1
		if status_prova == "CORRIDA" and total_voltas >= parametro_prova and not vencedor_detectado: status_prova, vencedor_detectado, relogio_inicial_texto = "BANDEIRADA", True, "FIM"
	return "ok"
if __name__ == '__main__':
	threading.Thread(target=processar_dados_serial, daemon=True).start()
	threading.Thread(target=atualizar_relogio_loop, daemon=True).start()
	app.run(host='0.0.0.0', port=5000, debug=False)

import time, random, urllib.request
print("[SIMULADOR ILS] Corrida e Classificacao ativas. Janela: 36s a 40s.")
relogio_karts = {1: time.time(), 2: time.time(), 3: time.time(), 4: time.time()}
while True:
	try:
		id_kart = random.randint(1, 4)
		tempo_volta = random.uniform(36.100, 39.900)
		relogio_karts[id_kart] += tempo_volta
		timestamp_passagem = int(relogio_karts[id_kart] * 1000)
		urllib.request.urlopen(f"http://localhost:5000/falso?id={id_kart}&tempo={timestamp_passagem}")
		time.sleep(random.uniform(1.0, 3.0))
	except: pass

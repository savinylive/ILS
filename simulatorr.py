import time, random, urllib.request
print("[SIMULADOR ILS] Grid ativo. Regulado de 36s a 38s com voltas iguais e ultrapassagens.")
relogio_karts = {1: time.time(), 2: time.time(), 3: time.time(), 4: time.time()}
id_karts = [1, 2, 3, 4]
while True:
	try:
		random.shuffle(id_karts)
		for id_kart in id_karts:
			tempo_volta = random.uniform(36.050, 37.950)
			relogio_karts[id_kart] += tempo_volta
			timestamp_passagem = int(relogio_karts[id_kart] * 1000)
			urllib.request.urlopen(f"http://localhost:5000/falso?id={id_kart}&tempo={timestamp_passagem}")
			time.sleep(random.uniform(1.0, 3.0))
		time.sleep(1)
	except: pass

import time, random, urllib.request
print("[SIMULADOR ILS] Grid de 4 Karts ativo no ritmo de ~37s.")
while True:
	try:
		id_kart = random.randint(1, 4)
		urllib.request.urlopen(f"http://localhost:5000/falso?id={id_kart}")
		time.sleep(random.uniform(0.5, 2.0))
	except: pass

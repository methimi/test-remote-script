import time

def calistir():
    sayac = 0
    while True:
        sayac += 1
        print(f"[uzak_script] calisiyor... sayac={sayac}")
        time.sleep(1)

print("[uzak_script] modul yuklendi, calistir() cagriliyor")
calistir()

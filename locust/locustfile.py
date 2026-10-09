import random
import uuid
from datetime import date, timedelta

from locust import HttpUser, between, task

PER_PAGE = 50
MAX_PAGINA = 1000  # rango de páginas que se piden al azar


def fecha_nacimiento_aleatoria() -> str:
    """Fecha aleatoria entre 1950 y 2010, en formato AAAA-MM-DD."""
    inicio = date(1950, 1, 1)
    fin = date(2010, 12, 31)
    dias = random.randint(0, (fin - inicio).days)
    return (inicio + timedelta(days=dias)).isoformat()


def usuario_aleatorio() -> dict:
    """Un usuario válido con un correo que nunca se repite."""
    return {
        "name": "Usuario Locust",
        "email": f"locust_{uuid.uuid4().hex}@loadtest.local",
        "password": "secret123",
        "birth_date": fecha_nacimiento_aleatoria(),
    }


class UsuarioAPI(HttpUser):
    # Cada usuario simulado espera entre 1 y 3 segundos entre tareas
    wait_time = between(1, 3)

    def on_start(self):
        # Se ejecuta una vez al nacer cada usuario simulado.
        # Sin este header, Laravel redirige en vez de responder 422 en JSON.
        self.client.headers.update({"Accept": "application/json"})

    # ---------- utilidades ----------

    def _params(self) -> dict:
        return {"page": random.randint(1, MAX_PAGINA), "per_page": PER_PAGE}

    def _validar_paginado(self, response, claves_extra=()):
        if response.status_code != 200:
            response.failure(f"Status inesperado: {response.status_code}")
            return
        try:
            body = response.json()
        except ValueError:
            response.failure("La respuesta no es JSON válido")
            return

        faltantes = [k for k in ("data", "total", *claves_extra) if k not in body]
        if faltantes:
            response.failure(f"Faltan claves en el JSON: {faltantes}")
        elif not isinstance(body["data"], list):
            response.failure("'data' no es una lista")
        else:
            response.success()

    # ---------- tareas ----------

    @task(4)
    def listar_usuarios(self):
        with self.client.get(
            "/api/users", params=self._params(),
            name="GET /api/users", catch_response=True,
        ) as r:
            self._validar_paginado(r)

    @task(3)
    def listar_correos(self):
        with self.client.get(
            "/api/users/emails", params=self._params(),
            name="GET /api/users/emails", catch_response=True,
        ) as r:
            self._validar_paginado(r)

    @task(2)
    def mayores_de_veinte(self):
        with self.client.get(
            "/api/users/over-twenty", params=self._params(),
            name="GET /api/users/over-twenty", catch_response=True,
        ) as r:
            self._validar_paginado(r, claves_extra=("cutoff_date",))

    @task(1)
    def crear_lote(self):
        payload = {"users": [usuario_aleatorio() for _ in range(3)]}
        with self.client.post(
            "/api/users/bulk", json=payload,
            name="POST /api/users/bulk", catch_response=True,
        ) as r:
            if r.status_code == 201:
                r.success()
            elif r.status_code == 422:
                r.failure(f"422 Validación (¿correo duplicado?): {r.text[:200]}")
            else:
                r.failure(f"Status inesperado: {r.status_code}")
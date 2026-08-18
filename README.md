# anomaly-alerts

Bot que detecta valores anómalos en una métrica y avisa. **Fase 1**: todo
corre sobre datos sintéticos, sin tocar ningún dato real. La conexión a la
fuente real (p.ej. BigQuery) se hace después, sustituyendo una única función.

## Qué hace

1. **Lee una métrica** — de momento una serie diaria sintética con
   tendencia, estacionalidad semanal y ruido (`generate_synthetic.py`).
2. **Detecta anomalías** — z-score sobre media móvil de 7 días: si un valor
   se desvía más de X desviaciones estándar de la media de los días
   anteriores, se marca (`anomaly.py`).
3. **Avisa** — por Telegram o email, con un mensaje del tipo *"⚠️ instalaciones
   cayó un 24% respecto a la media esperada"* (`notify.py`).
4. **Orquesta todo** en un único comando (`run.py`).

## Estructura

```
anomaly-alerts/
├── data/
│   └── synthetic_metric.csv   # datos falsos generados por el script
├── src/
│   ├── generate_synthetic.py  # crea la serie temporal de prueba
│   ├── anomaly.py             # lógica de detección (z-score / IQR)
│   ├── notify.py              # envío de alertas (Telegram / email)
│   └── run.py                 # orquesta: lee → detecta → notifica
├── config.yaml                # umbrales, canal de notificación, frecuencia
└── requirements.txt
```

## Uso rápido

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cd src
python run.py --plot              # detecta sobre data/synthetic_metric.csv
python run.py --generate --plot   # regenera los datos sintéticos primero
python run.py --no-notify         # detecta pero no intenta enviar alertas
```

Sin credenciales configuradas, `run.py` detecta igual y simplemente imprime
las alertas por consola en vez de enviarlas — no hace falta configurar nada
para probar el pipeline de principio a fin.

## Datos sintéticos

`generate_synthetic.py` crea 90 días de una métrica ficticia ("instalaciones")
con:

- Tendencia suave creciente.
- Estacionalidad semanal (más actividad entre semana, algo menos el
  fin de semana) — con amplitud contenida a propósito, ver más abajo.
- Ruido gaussiano.
- 4 anomalías forzadas en fechas fijas (2 picos, 2 caídas) para poder
  verificar que el detector las encuentra.

```bash
python src/generate_synthetic.py --plot
# -> data/synthetic_metric.csv
# -> data/synthetic_metric.png (serie con las anomalías forzadas marcadas)
```

## Detección (`anomaly.py`)

Método por defecto: **z-score sobre media móvil**. Para cada día se calcula
la media y desviación estándar de los `window_days` días *anteriores* (nunca
incluye el propio día, para que un pico no infle su propia línea base). Si el
valor se desvía `threshold_std` veces esa desviación estándar, se marca como
anomalía.

También está implementado el método **IQR** (rango intercuartílico),
pensado como alternativa para métricas con outliers naturales frecuentes
donde el z-score dispara demasiado. Se selecciona con `detection.method` en
`config.yaml`.

### Por qué el umbral por defecto es 3.0 y no 2.0

Con un umbral de 2 desviaciones estándar, ~1 de cada 20 días *normales* lo
supera solo por azar estadístico (así funciona una campana de Gauss). Sobre
~90 días de datos eso ya produce 2-3 falsos positivos en la serie sintética,
aunque no haya ninguna anomalía real. Con 3.0σ las 4 anomalías forzadas
quedan muy por encima (|z| ≥ 6.7) y el ruido normal se queda por debajo
(|z| < 2.8): separación limpia, cero falsos positivos, cero anomalías
forzadas sin detectar. Ajustable en `config.yaml` si tu métrica real es más
o menos ruidosa.

## Notificación (`notify.py`)

Dos canales, elegidos con `notification.channel` en `config.yaml`:

- **Telegram**: crea un bot con [@BotFather](https://t.me/BotFather), copia
  el token y el `chat_id` (por ejemplo hablando con
  [@userinfobot](https://t.me/userinfobot) o mirando la respuesta de
  `getUpdates`), y rellénalos en `config.yaml`.
- **Email**: credenciales SMTP simples (host, puerto, usuario, contraseña,
  remitente, destinatario).

Con `channel: none` (valor por defecto) las alertas solo se imprimen por
consola — útil para probar sin montar nada todavía. Si faltan credenciales
del canal elegido, `notify.py` avisa por consola y no lanza ninguna
excepción: el resto del pipeline sigue funcionando.

## `config.yaml`

```yaml
data:
  path: data/synthetic_metric.csv
  metric_name: "instalaciones"

detection:
  method: zscore          # zscore | iqr
  window_days: 7
  threshold_std: 3.0
  iqr_multiplier: 1.5

notification:
  channel: none            # telegram | email | none
  telegram:
    bot_token: ""
    chat_id: ""
  email:
    smtp_host: ""
    smtp_port: 587
    username: ""
    password: ""
    from_addr: ""
    to_addr: ""

schedule:
  frequency: daily         # informativo: cada cuánto se espera correr run.py
```

## Próximos pasos (fuera de esta fase)

- Sustituir `load_data()` en `src/run.py` por una query real (p.ej.
  BigQuery) en lugar de leer `data/synthetic_metric.csv`.
- Programar `run.py` con cron/scheduler según `schedule.frequency`.
- Correlación con variables externas (clima, precio, etc.) si hace falta
  explicar el "por qué" de una anomalía, no solo detectarla.

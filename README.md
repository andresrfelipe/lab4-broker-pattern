# Lab 4 — Broker Pattern

Este repositorio implementa el patrón Broker para desacoplar un productor y un consumidor mediante una cola de mensajes. La solución se compone de cuatro componentes orquestados con Docker Compose.

## Arquitectura

El sistema sigue el patrón Broker: el productor publica mensajes a una cola en RabbitMQ, el consumidor los procesa de forma asíncrona y los persiste en MongoDB. El productor y el consumidor no se comunican directamente.

### Componentes

| Componente | Rol | Tecnología | Ubicación |
|---|---|---|---|
| Servicio de Publicación (Componente 2) | Productor. Expone una API HTTP para publicar ítems a la cola. | Python, FastAPI, aio-pika | `broker-pattern/component-2/` |
| Broker de Mensajes (Componente 1) | Broker. Almacena mensajes en la cola durable `items_queue`. | RabbitMQ 3 (management) | Imagen `rabbitmq:3-management` |
| Servicio de Procesamiento (Componente 3) | Consumidor/Worker. Consume mensajes de la cola y los guarda en la BD. | Python, aio-pika, motor | `broker-pattern/component-3/` |
| Base de Datos (Componente 4) | Almacenamiento. Persiste los ítems procesados. | MongoDB | Imagen `mongo` |

### Vista de Componentes y Conectores (C&C)

Los conectores principales son:
- `K1`: HTTP/JSON `POST /items` (Cliente → Servicio de Publicación)
- `K2`: Publicación (`pub`) (Servicio de Publicación → Broker, AMQP)
- `K3`: Cola durable `items_queue` (dentro del Broker)
- `K4`: Consumo + ack (`sub`) (Broker → Servicio de Procesamiento, AMQP)
- `K5`: `insert_one` (Servicio de Procesamiento → Base de Datos, MongoDB wire)

Ver más detalles en [broker-pattern/docs/vistas-arquitectonicas.md](broker-pattern/docs/vistas-arquitectonicas.md).

### Vista de Despliegue

Todos los componentes se despliegan en contenedores Docker en la misma red `bridge` creada por Docker Compose. El nombre de contenedor se usa para la resolución DNS entre servicios.

| Componente | Contenedor | Imagen/Build | Puertos (host:contenedor) |
|---|---|---|---|
| Servicio de Publicación | `component-2` | build `./component-2` (python:3.11-slim) | `8000:8000` |
| Broker de Mensajes | `component-1` | `rabbitmq:3-management` | `5672:5672`, `15672:15672` |
| Servicio de Procesamiento | `component-3` | build `./component-3` (python:3.11-slim) | — |
| Base de Datos | `component-4` | `mongo` | `27017:27017` |

## Configuración

Variables de entorno usadas:

| Componente | Variables | Valor por defecto |
|---|---|---|
| component-2 | `RABBIT_URL`, `QUEUE_NAME` | `amqp://guest:guest@component-1:5672/`, `items_queue` |
| component-3 | `RABBIT_URL`, `QUEUE_NAME`, `MONGO_URL` | `amqp://guest:guest@component-1:5672/`, `items_queue`, `mongodb://component-4:27017` |

Orden de arranque (según `docker-compose.yml`): `component-2` y `component-3` esperan a que `component-1` esté `healthy`. `component-3` espera también a `component-4` con `healthy`.

## Cómo ejecutar

Desde el directorio `broker-pattern/`:

```bash
docker compose up --build
```

Para detener y limpiar contenedores/volúmenes:
```bash
docker compose down -v
```

## Uso de la API

El servicio de publicación expone `POST /items` en `http://localhost:8000`.

### Ejemplo con curl

```bash
curl -X POST http://localhost:8000/items \
  -H "Content-Type: application/json" \
  -d '{"name": "SwArch", "description": "2026-II"}'
```

Respuesta esperada:
```json
{"status": "published"}
```

## Verificación

### Ver logs del worker
```bash
docker logs -f component-3
```
Cuando un mensaje es procesado correctamente verás algo como:
```
[x] Item stored: {'name': 'SwArch', 'description': '2026-II'}
```

### Ver mensajes en RabbitMQ
Accede al panel de administración en [http://localhost:15672](http://localhost:15672) (usuario/contraseña: `guest`/`guest`). La cola `items_queue` es durable.

### Ver documentos en MongoDB
```bash
docker exec -it component-4 mongosh
```
```js
use broker_lab
db.items.find().pretty()
```

## Pruebas realizadas (resumen)

| Prueba | Resultado |
|---|---|
| Consumo de mensajes | Correcto. Mensaje procesado con ack, cola vuelve a 0. |
| Almacenamiento en MongoDB | Documento persistido en `broker_lab.items`. |
| Mensajes pendientes al caerse el consumidor | Si `component-3` está caído, los mensajes quedan en cola y se procesan al reiniciarlo. |
| Reconexión del broker | `component-3` reintenta cada 5s y se reconecta si `component-1` se reinicia. Cola durable. |
| Integración completa | Publicación vía API → cola → worker → MongoDB funciona correctamente. |
| Mensaje no JSON | El worker sigue vivo; el mensaje se descarta con traceback en logs (comportamiento observado, no modificado). |

## Estructura del proyecto

```
lab4-broker-pattern/
├── README.md
├── broker-pattern/
│   ├── docker-compose.yml
│   ├── component-1/        # (imagen: rabbitmq:3-management)
│   ├── component-2/        # Productor FastAPI
│   │   ├── app/main.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── component-3/        # Consumidor Worker
│   │   ├── worker/worker.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── component-4/        # (imagen: mongo)
│   └── docs/
│       ├── diagramas/      # Imágenes de las vistas
│       └── vistas-arquitectonicas.md
└── [archivos de laboratorio .md/.pdf/.png]
```

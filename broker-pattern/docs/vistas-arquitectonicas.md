# Laboratorio 4 — Vistas arquitectónicas (patrón Broker)

## 1. Vista de Componentes y Conectores (C&C)

![Vista C&C](diagramas/vista-cc.png)

**Componentes**

| Componente | Rol en el PDF | Tecnología | Puerto |
|---|---|---|---|
| Servicio de Publicación | Producer (Componente 2) | Python, FastAPI, aio-pika | HTTP 8000 |
| Broker de Mensajes | Broker (Componente 1) | RabbitMQ 3 (management) | AMQP 5672, dashboard 15672 |
| Servicio de Procesamiento | Consumer / Worker (Componente 3) | Python, aio-pika, motor | — (solo cliente) |
| Base de Datos | Database (Componente 4) | MongoDB | 27017 |

El Broker contiene la cola durable `items_queue`. El Cliente (navegador o `curl`) es externo al sistema.

**Conectores**

| Id | Conector | Entre | Protocolo |
|---|---|---|---|
| K1 | HTTP/JSON `POST /items` | Cliente → Servicio de Publicación | HTTP |
| K2 | Publicación (`pub`) | Servicio de Publicación → Broker | AMQP |
| K4 | Consumo + ack (`sub`) | Broker → Servicio de Procesamiento | AMQP |
| K5 | `db_connector` (`insert_one`) | Servicio de Procesamiento → Base de Datos | MongoDB wire |

**Nota sobre K3:** K3 corresponde a la cola durable `items_queue`, ubicada dentro del Broker de Mensajes. No es un componente de despliegue independiente, por eso no aparece como contenedor en la vista de despliegue.

**Idea clave:** el Servicio de Publicación y el Servicio de Procesamiento no se comunican directamente; lo hacen a través del Broker (RabbitMQ) y comparten un contrato de mensajería común (mensajes JSON con los campos `name` y `description`, publicados en `items_queue`). Si el consumidor está caído, los mensajes esperan en la cola.

---

## 2. Vista de Despliegue

![Vista de despliegue](diagramas/vista-despliegue.png)

Cada componente se despliega en un contenedor Docker, todos en la misma red *bridge* que crea Docker Compose (`broker-pattern_default`), donde se resuelven por nombre.

| Componente | Contenedor | Imagen | Puertos publicados (host:contenedor) |
|---|---|---|---|
| Servicio de Publicación | `component-2` | build `./component-2` (python:3.11-slim) | 8000:8000 |
| Broker de Mensajes | `component-1` | `rabbitmq:3-management` | 5672:5672, 15672:15672 |
| Servicio de Procesamiento | `component-3` | build `./component-3` (python:3.11-slim) | ninguno |
| Base de Datos | `component-4` | `mongo` | 27017:27017 |

**Infraestructura:** host Windows 11 + WSL 2, Docker Engine y Docker Compose.
**Configuración (variables de entorno):** `RABBIT_URL=amqp://guest:guest@component-1:5672/`, `QUEUE_NAME=items_queue`, `MONGO_URL=mongodb://component-4:27017`.
**Orden de arranque:** `component-2` y `component-3` esperan a que `component-1` esté *healthy*; `component-3` también espera a `component-4`.

---

## 3. Pruebas realizadas

Ejecutadas con Docker Compose desde `broker-pattern/`.

| Prueba | Procedimiento | Resultado |
|---|---|---|
| Consumo de mensajes | Publicar `{"name":"SwArch","description":"2026-II"}` en `items_queue` desde la API de gestión de RabbitMQ | Log `[x] Item stored: {'name': 'SwArch', 'description': '2026-II'}`; cola en 0 (ack correcto) |
| Almacenamiento en MongoDB | `docker exec component-4 mongosh` → `broker_lab.items.find()` | Documento presente en `broker_lab.items` |
| Mensajes pendientes | Detener `component-3`, publicar 3 mensajes, reiniciarlo | Los 3 quedaron en cola con 0 consumidores y se procesaron al volver |
| Reconexión | `docker restart component-1` | El worker reintentó cada 5 s, reconectó solo; la cola siguió durable con 1 consumidor |
| Integración completa | `curl -X POST http://localhost:8000/items ...` con los 4 contenedores | Respuesta `{"status":"published"}`, log del worker y documento en MongoDB |
| Mensaje no JSON (observación) | Publicar texto plano | El worker sigue vivo; el mensaje se descarta con traceback en el log. No es requisito del laboratorio y no se modificó |

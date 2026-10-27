import asyncio
import aio_pika
import json
import motor.motor_asyncio
import os

RABBIT_URL = os.environ.get("RABBIT_URL", "amqp://guest:guest@component-1:5672/")
QUEUE_NAME = os.environ.get("QUEUE_NAME", "items_queue")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://component-4:27017")

mongo_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL)
db = mongo_client["broker_lab"]
collection = db["items"]


async def process_message(message: aio_pika.IncomingMessage):
    async with message.process():
        data = json.loads(message.body)
        await collection.insert_one(dict(data))
        print(f"[x] Item stored: {data}", flush=True)


async def main():
    connection = await aio_pika.connect_robust(RABBIT_URL, fail_fast=False)
    channel = await connection.channel()
    queue = await channel.declare_queue(QUEUE_NAME, durable=True)
    await queue.consume(process_message)
    print("[x] Waiting for messages...", flush=True)
    return connection


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    connection = loop.run_until_complete(main())
    try:
        loop.run_forever()
    finally:
        loop.run_until_complete(connection.close())

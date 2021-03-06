import logging
from threading import Thread
from typing import List, Optional

import paho.mqtt.client as mqtt

from mqtt_utils.messages import utils
from mqtt_utils.messages.mqtt_message import MQTTMessage
from mqtt_utils.messages.empty import Empty
from mqtt_utils.mqtt_client import MQTTClient


class MessageManager(Thread):
    def __init__(self, messages: List[MQTTMessage],
                 error_topic: Optional[str] = None):
        super().__init__()
        self._mqtt_client = MQTTClient()
        self._mqtt_client.registered_topics = [msg.topic for msg in messages]
        self._messages: List[MQTTMessage] = messages + [Empty()]
        self._error_topic = error_topic
        self._logger = logging.getLogger(self.__class__.__name__)
        self._message_queue = self._mqtt_client.message_queue
        self._publish_method = self._mqtt_client.publish
        self._stop_thread = False

    def subscribe_messages(self, messages):
        for message in messages:
            self._messages.append(message)

        self._mqtt_client.subscribe([msg.topic for msg in messages])

    def update_credentials(self, user, password):
        self._mqtt_client.update_username_password(user, password)

    def connect(self, address, port):
        self._mqtt_client.connect(address, port)

    def publish(self, topic, payload):
        self._logger.debug(f'Publishing messages topic: {topic}, '
                           f'payload: {payload}')
        self._publish_method(topic, payload)

    def _execute_message(self, topic: str, payload: str):
        message = self._check_message(topic)
        if not message:
            return

        try:
            payload_dict = utils.payload_from_json(payload)
            message.execute(payload_dict)
        except Exception as ex:
            self._logger.error(f'Error raised during execution of messages. '
                               f'Exception: {ex}')
            raise ex

    def _check_message(self, topic) -> Optional[MQTTMessage]:
        """
        Check if topic is registered and payload is properly formatted
        """
        self._logger.debug(f'Searching for messages topic: {topic}')
        for message in self._messages:
            if message.topic == topic:
                return message

        error_message = \
            f'Received messages not registered. Registered topics: ' \
            f'{[message.topic for message in self._messages]} got: {topic}'

        self._logger.warning(error_message)

        return None

    def run(self) -> None:
        """
        Get messages received by mqtt_utils, check the topic and payload,
        and get MQTTMessage object, then run execute() method from him
        :return:
        """
        while not self._stop_thread:
            message: mqtt.MQTTMessage = self._message_queue.get()
            self._logger.debug(f'Got messages topic: {message.topic} '
                               f'payload: {message.payload}')
            try:
                self._execute_message(message.topic, message.payload)
            except BaseException as ex:
                if self._error_topic:
                    self.publish(self._error_topic, ex)
        self._logger.debug('Exiting')

    def loop_forever(self):
        self._mqtt_client.loop_forever()

    def stop(self):
        self._logger.debug('Stopping')
        self._stop_thread = True
        self._message_queue.put(Empty())

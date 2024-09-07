import json
from channels.generic.websocket import WebsocketConsumer
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from asgiref.sync import async_to_sync
from .models import GroupMessage, ChatGroup

class ChatroomConsumer(WebsocketConsumer):
    def connect(self):
        # Get user and chatroom details
        self.user = self.scope['user']
        self.chatroom_name = self.scope['url_route']['kwargs']['chatroom_name']
        self.chatroom = get_object_or_404(ChatGroup, group_name=self.chatroom_name)

        # Add user to the chatroom group
        async_to_sync(self.channel_layer.group_add)(
            self.chatroom_name, 
            self.channel_name
        )
        
        # Accept connection if user is authenticated
        if self.user.is_authenticated:
            self.accept()
        else:
            self.close()

    def disconnect(self, close_code):
        # Remove the user from the chatroom group on disconnect
        async_to_sync(self.channel_layer.group_discard)(
            self.chatroom_name, 
            self.channel_name
        )

    def receive(self, text_data):
        # Parse the incoming message
        text_data_json = json.loads(text_data)
        body = text_data_json.get('body')

        # Save message to the database
        if body and self.user.is_authenticated:
            message = GroupMessage.objects.create(
                body=body,
                author=self.user,
                group=self.chatroom
            )

            # Create an event to send the message to the group
            event = {
                'type': 'message_handler',
                'message_id': message.id
            }

            # Broadcast the message to the group
            async_to_sync(self.channel_layer.group_send)(
                self.chatroom_name, 
                event
            )
        else:
            # Send an error message back to the user
            self.send(text_data=json.dumps({'error': 'Authentication failed or empty message.'}))

    def message_handler(self, event):
        # Get the message by ID from the event
        message_id = event['message_id']
        message = GroupMessage.objects.get(id=message_id)

        # Render the message to HTML
        context = {
            'message': message,
            'user': self.user,
        }
        html = render_to_string("a_rtchat/partials/chat_message_p.html", context=context)

        # Send the rendered HTML back to the WebSocket
        self.send(text_data=html)

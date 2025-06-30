from django.contrib import admin
from .models import UploadedPDF, Conversation, Message

class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ('role', 'content', 'timestamp')

class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'document', 'created_at')
    inlines = [MessageInline]

class UploadedPDFAdmin(admin.ModelAdmin):
    list_display = ('file', 'uploaded_at')

admin.site.register(UploadedPDF, UploadedPDFAdmin)
admin.site.register(Conversation, ConversationAdmin)
admin.site.register(Message)

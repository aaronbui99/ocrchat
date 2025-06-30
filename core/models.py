from django.db import models

class UploadedPDF(models.Model):
    file = models.FileField(upload_to='pdfs/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    extracted_text = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.file.name} (Uploaded: {self.uploaded_at})"

class Conversation(models.Model):
    MODEL_CHOICES = [
        ('gpt-4', 'GPT-4'),
        ('gpt-4-turbo', 'GPT-4 Turbo'),
    ]
    
    document = models.ForeignKey(UploadedPDF, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    model_name = models.CharField(max_length=50, choices=MODEL_CHOICES, default='gpt-4')
    
    def __str__(self):
        return f"Conversation {self.id} - {self.created_at}"

class Message(models.Model):
    ROLE_CHOICES = [
        ('user', 'User'),
        ('ai', 'AI'),
    ]
    
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.role}: {self.content[:50]}..."
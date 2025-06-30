from django.shortcuts import render, redirect
from django.core.files.storage import default_storage
from pdf2image import convert_from_path
import pytesseract, os
from .models import UploadedPDF, Conversation, Message

# Configure this for Windows
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# LangChain setup
from langchain_openai import ChatOpenAI
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory
from dotenv import load_dotenv
from PIL import Image

load_dotenv()

# We'll create the LLM instance dynamically based on the selected model
def get_chat_chain(model_name='gpt-4'):
    llm = ChatOpenAI(
        temperature=0.7, 
        api_key=os.getenv("OPENAI_API_KEY"),
        model_name=model_name
    )
    memory = ConversationBufferMemory()
    return ConversationChain(llm=llm, memory=memory)

def extract_text(file_path, content_type):
    text = ""
    if "pdf" in content_type:
        images = convert_from_path(file_path)
        for img in images:
            text += pytesseract.image_to_string(img)
    elif "image" in content_type:
        img = Image.open(file_path)
        text = pytesseract.image_to_string(img)
    return text

def upload_file(request):
    global extracted_text, current_document, current_conversation
    
    # Get the current conversation from the session if it exists
    conversation_id = request.session.get('conversation_id')
    conversation = None
    messages = []
    
    # Get all conversations for the dropdown
    all_conversations = Conversation.objects.all().order_by('-created_at')
    
    if conversation_id:
        try:
            conversation = Conversation.objects.get(id=conversation_id)
            messages = Message.objects.filter(conversation=conversation).order_by('timestamp')
            
            # If we have a conversation but no extracted_text, try to get it from the document
            if 'extracted_text' not in globals() or not extracted_text:
                if conversation.document:
                    # First try to get the extracted text from the database
                    if conversation.document.extracted_text:
                        extracted_text = conversation.document.extracted_text
                        request.session['extracted_text'] = extracted_text
                    else:
                        # If not in database, extract it and save it
                        document_path = default_storage.path(conversation.document.file.name)
                        content_type = ""
                        if document_path.lower().endswith('.pdf'):
                            content_type = "application/pdf"
                        elif document_path.lower().endswith(('.jpg', '.jpeg', '.png')):
                            content_type = "image/jpeg"
                        
                        if content_type:
                            extracted_text = extract_text(document_path, content_type)
                            # Save the extracted text to the database
                            conversation.document.extracted_text = extracted_text
                            conversation.document.save()
                            request.session['extracted_text'] = extracted_text
        except Conversation.DoesNotExist:
            # Clear the invalid conversation ID
            request.session.pop('conversation_id', None)
    
    if request.method == 'POST' and request.FILES.get('file'):
        uploaded = request.FILES['file']
        content_type = uploaded.content_type
        file_path = default_storage.save(uploaded.name, uploaded)
        full_path = default_storage.path(file_path)

        extracted_text = extract_text(full_path, content_type)
        
        # Save the uploaded document to the database with extracted text
        current_document = UploadedPDF.objects.create(
            file=file_path,
            extracted_text=extracted_text
        )
        
        # Get the selected model (default to gpt-4 if not specified)
        model_name = request.POST.get('model', 'gpt-4')
        
        # Create a new conversation for this document with the selected model
        current_conversation = Conversation.objects.create(
            document=current_document,
            model_name=model_name
        )
        
        # Store this conversation ID in the session
        request.session['conversation_id'] = current_conversation.id
        
        # Store extracted text in the session
        request.session['extracted_text'] = extracted_text
        
        # Store the model name in the session
        request.session['model_name'] = model_name

        # Redirect to the same page to refresh with the new conversation
        return redirect('upload')
    
    # Get extracted_text from session if available
    extracted_text_to_display = None
    if 'extracted_text' in request.session:
        extracted_text_to_display = request.session['extracted_text']
    
    # Get model name from session or from conversation
    model_name = request.session.get('model_name')
    if not model_name and conversation:
        model_name = conversation.model_name
    
    # Format the model name for display
    model_display_name = None
    if model_name:
        model_display_map = {
            'gpt-4': 'GPT-4',
            'gpt-4-turbo': 'GPT-4 Turbo'
        }
        model_display_name = model_display_map.get(model_name, model_name)
    
    return render(request, 'core/combined.html', {
        'conversation_id': conversation_id,
        'messages': messages,
        'extracted_text': extracted_text_to_display,
        'model_name': model_display_name,
        'all_conversations': all_conversations
    })

def new_chat(request):
    """Clear the current conversation from the session to start a new chat"""
    if request.method == 'POST':
        # Clear conversation-related session data
        request.session.pop('conversation_id', None)
        request.session.pop('extracted_text', None)
        request.session.pop('model_name', None)
    
    return redirect('upload')

def switch_conversation(request, conversation_id):
    """Switch to a different conversation"""
    try:
        # Check if the conversation exists
        conversation = Conversation.objects.get(id=conversation_id)
        
        # Update the session with the new conversation
        request.session['conversation_id'] = conversation.id
        
        # If the conversation has a document with extracted text, load it
        if conversation.document and conversation.document.extracted_text:
            request.session['extracted_text'] = conversation.document.extracted_text
        
        # Store the model name
        request.session['model_name'] = conversation.model_name
        
    except Conversation.DoesNotExist:
        # If conversation doesn't exist, just redirect without changing session
        pass
    
    return redirect('upload')

def chat_view(request):
    global extracted_text
    answer = None
    
    # Get the current conversation from the session
    conversation_id = request.session.get('conversation_id')
    if not conversation_id:
        # If no conversation exists, redirect to upload
        return redirect('upload')
    
    try:
        conversation = Conversation.objects.get(id=conversation_id)
    except Conversation.DoesNotExist:
        # If conversation doesn't exist, redirect to upload
        return redirect('upload')
    
    # Get previous messages for this conversation
    messages = Message.objects.filter(conversation=conversation).order_by('timestamp')
    
    # Get extracted_text from session, database, or extract it if needed
    if 'extracted_text' in request.session:
        extracted_text = request.session['extracted_text']
    elif conversation.document and conversation.document.extracted_text:
        # Get from database
        extracted_text = conversation.document.extracted_text
        request.session['extracted_text'] = extracted_text
    elif 'extracted_text' not in globals() or not extracted_text:
        if conversation.document:
            document_path = default_storage.path(conversation.document.file.name)
            content_type = ""
            if document_path.lower().endswith('.pdf'):
                content_type = "application/pdf"
            elif document_path.lower().endswith(('.jpg', '.jpeg', '.png')):
                content_type = "image/jpeg"
            
            if content_type:
                extracted_text = extract_text(document_path, content_type)
                # Save to database
                conversation.document.extracted_text = extracted_text
                conversation.document.save()
                request.session['extracted_text'] = extracted_text
    
    if request.method == 'POST':
        question = request.POST.get('message')
        
        # Save the user's message to the database
        Message.objects.create(
            conversation=conversation,
            role='user',
            content=question
        )
        
        # Get the model name from the conversation
        model_name = conversation.model_name
        
        # Create a chat chain with the selected model
        chat_chain = get_chat_chain(model_name)
        
        # Create a system prompt that instructs the model to use the extracted text
        system_prompt = f"""You are an AI assistant that helps users understand documents. 
            You have been provided with the text extracted from a document using OCR.
            Use this extracted text to answer the user's questions.
            If the answer cannot be found in the extracted text, say so clearly.

            Extracted text:
            {extracted_text}
        """
        
        # Add the system prompt to the chat chain's memory
        chat_chain.memory.chat_memory.add_user_message(system_prompt)
        
        # Get the answer from the model
        answer = chat_chain.run(question)
        
        # Save the AI's response to the database
        Message.objects.create(
            conversation=conversation,
            role='ai',
            content=answer
        )
        
        # Redirect back to the upload page which now shows the combined view
        return redirect('upload')
    
    # This should rarely be reached directly, but just in case
    return redirect('upload')

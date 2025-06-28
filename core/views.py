from django.shortcuts import render, redirect
from django.core.files.storage import default_storage
from pdf2image import convert_from_path
import pytesseract, os

# Configure this for Windows
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# LangChain setup
from langchain_openai import ChatOpenAI
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory
from dotenv import load_dotenv
from PIL import Image

load_dotenv()
llm = ChatOpenAI(temperature=0.7, api_key=os.getenv("OPENAI_API_KEY"))
memory = ConversationBufferMemory()
chat_chain = ConversationChain(llm=llm, memory=memory)

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
    global extracted_text
    if request.method == 'POST' and request.FILES.get('file'):
        uploaded = request.FILES['file']
        content_type = uploaded.content_type
        file_path = default_storage.save(uploaded.name, uploaded)
        full_path = default_storage.path(file_path)

        extracted_text = extract_text(full_path, content_type)

        return redirect('chat')
    return render(request, 'core/upload.html')

def chat_view(request):
    global extracted_text
    answer = None
    if request.method == 'POST':
        question = request.POST.get('message')
        combined_prompt = f"PDF context:\n{extracted_text}\n\nUser question: {question}"
        answer = chat_chain.run(combined_prompt)
    return render(request, 'core/chat.html', {'response': answer})

import discord
from discord.ext import commands
import google.generativeai as genai
import fitz  # PyMuPDF
import io
import os

# ================= 설정 =================
DISCORD_TOKEN = os.environ.get('DISCORD_BOT_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-3.8-flash')

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)
# ========================================

@bot.event
async def on_ready():
    print(f'✅ 봇이 로그인했습니다: {bot.user}')
    await bot.change_presence(activity=discord.Game(name="!요약 | 문서 분석"))

@bot.command(name="요약")
async def summarize_doc(ctx):
    # 1. 파일 첨부 여부 확인
    if not ctx.message.attachments:
        await ctx.reply("요약할 문서 파일(.txt 또는 .pdf)을 첨부하고 `!요약`을 입력해주세요.")
        return

    attachment = ctx.message.attachments[0]
    
    # 2. 디스코드 업로드 용량 제한 확인 (예: 25MB 제한)
    if attachment.size > 25 * 1024 * 1024:
        await ctx.reply("❌ 파일 용량이 너무 큽니다. 25MB 이하의 파일만 지원합니다.")
        return

    # 3. 진행 상태 안내 메시지 전송 (UX 향상)
    status_msg = await ctx.reply(f"📥 `{attachment.filename}` 파일을 읽는 중입니다. 문서 길이에 따라 10초~1분 정도 소요될 수 있습니다...")

    try:
        # 타이핑 효과를 주어 봇이 멈춘 것이 아님을 보여줌
        async with ctx.typing():
            text = ""
            
            # 4. 파일 확장자에 따른 텍스트 추출
            if attachment.filename.lower().endswith('.txt'):
                file_bytes = await attachment.read()
                text = file_bytes.decode('utf-8', errors='ignore')
                
            elif attachment.filename.lower().endswith('.pdf'):
                file_bytes = await attachment.read()
                pdf_document = fitz.open(stream=file_bytes, filetype="pdf")
                for page in pdf_document:
                    text += page.get_text()
                pdf_document.close()
                
            else:
                await status_msg.edit(content="❌ 현재는 `.txt`와 `.pdf` 파일만 지원합니다.")
                return

            # 텍스트 추출 실패 시 (이미지로만 된 PDF 등)
            if not text.strip():
                await status_msg.edit(content="❌ 문서에서 텍스트를 추출할 수 없습니다. 스캔된 이미지 기반 PDF일 수 있습니다.")
                return

            await status_msg.edit(content="🧠 AI가 문서를 분석하고 요약하는 중입니다...")

            # 5. Gemini AI에게 요약 요청
            prompt = f"다음 문서의 핵심 내용을 3~5개의 주요 단락으로 나누어 상세히 요약해줘. 가독성 좋게 마크다운과 글머리 기호를 사용해줘:\n\n{text}"
            response = await model.generate_content_async(prompt)
            summary = response.text

            # 6. 글자 수 제한 (2000자) 스마트 대응
            if len(summary) > 1900:
                # 결과가 너무 길면 메모리 상에서 마크다운(.md) 파일로 변환
                summary_file = io.BytesIO(summary.encode('utf-8'))
                discord_file = discord.File(fp=summary_file, filename=f"요약결과_{attachment.filename}.md")
                
                # 메시지로는 요약본 앞부분(미리보기)만 제공
                preview = summary[:500] + "\n\n... *(내용이 길어 전체 요약본은 아래 파일로 첨부했습니다!)*"
                await status_msg.edit(content=f"✅ **요약이 완료되었습니다! (미리보기)**\n\n{preview}")
                await ctx.send(file=discord_file)
            else:
                # 1900자 이하면 그냥 메시지로 바로 출력
                await status_msg.edit(content=f"✅ **요약 결과:**\n\n{summary}")

    except Exception as e:
        # 7. 예외(에러) 처리
        await status_msg.edit(content=f"❌ 요약 처리 중 오류가 발생했습니다.\n에러 내용: `{str(e)}`")

# 봇 실행
bot.run(DISCORD_TOKEN)
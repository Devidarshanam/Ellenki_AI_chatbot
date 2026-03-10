import re

from flask import Blueprint, render_template, request, jsonify

from . import retrieval_service, recommender  # we use recommender.courses as well

from .services import retrieval, lm_studio


bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    return render_template("chat.html")


def classify_intent(text: str) -> str:
    text_l = text.lower()

    # 1) Check for course suggestion FIRST
    if any(k in text_l for k in [
        "which course", "which branch", "which stream",
        "suggest course", "suggest branch", "suggest me a course",
        "suggest me branch", "suggest branch for me",
        "what course", "what branch",
        "i like", "i love",
        "my interest", "my interests",
        "i am interested in", "i'm interested in",
        "i have interest in", "i have deep interest in",
        "interested in ai", "interested in ml",
        "suited for me", "suit me", "best for me", "better for me",
        "passion", "passionate", "enjoy", "prefer"
    ]):
        return "course_recommendation"

    # 2) Then college-info type questions
    if any(k in text_l for k in [
        "ellenki", "college", "btech", "mtech", "mba", "mca",
        "admission", "admissions", "fee", "fees",
        "hostel", "transport",
        "placements", "placement", "jntuh", "patancheru", "near bhel",
        "chairman", "principal", "infrastructure", "library",
        "courses are available", "branches are available"
    ]):
        return "college_info"

    # 3) Otherwise, general chat
    return "general"


def _shorten_snippet(snippet: str, max_sentences: int = 4, max_len: int = 500) -> str:
    """
    Smart shortening:
    - Keeps short snippets fully (<= max_len)
    - Uses regex to avoid splitting on Dr., E., B.Tech., M.Tech.
    - Keeps 3–4 real sentences for longer paragraphs
    """

    text = snippet.strip().replace("\n", " ")

    # 1) If text already short, return full text
    if len(text) <= max_len:
        return text

    # 2) FAQ style format
    if "A:" in text:
        part = text.split("A:", 1)[1].strip()
        if len(part) <= max_len:
            return part
        text = part

    # 3) Smart sentence splitting via regex
    # Splits only when a period is followed by a space and a capital letter
    # avoids "Dr.", "Prof.", "E.", "B.Tech.", "M.Tech."
    sentences = re.split(r'(?<=[^.])\. (?=[A-Z])', text)

    # remove empty pieces
    sentences = [s.strip() for s in sentences if s.strip()]

    # 4) Keep first 4 meaningful sentences
    short = ". ".join(sentences[:max_sentences])
    if short and not short.endswith("."):
        short += "."

    return short


def _extract_answer_from_faq(snippet: str) -> str:
    """
    Extract just the answer from FAQ format.
    Removes "Q: ..." and returns clean "A: ..." answer.
    """
    text = snippet.strip()
    
    # If it has FAQ format with "A:", extract just the answer part
    if "A:" in text:
        answer = text.split("A:", 1)[1].strip()
        return answer
    
    # Otherwise return the text as-is
    return text



def _list_programmes(level: str) -> str:
    """
    Build a short bullet list for B.Tech / M.Tech / Diploma etc.
    level: "btech", "mtech", "diploma", "pg"
    """
    courses = recommender.courses
    items = []

    if level == "btech":
        for c in courses:
            if c["code"] in {"CSE", "CSD", "CSM", "CSC", "ECE", "EEE", "ME", "CE"}:
                items.append(c["name"])
    elif level == "mtech":
        for c in courses:
            if c["code"].startswith("MTECH-"):
                items.append(c["name"])
    elif level == "diploma":
        for c in courses:
            if c["code"].startswith("DIP-"):
                items.append(c["name"])
    elif level == "pg":
        for c in courses:
            if c["code"] in {"MBA", "MCA"}:
                items.append(c["name"])

    if not items:
        return "I don't have structured information for that level yet."

    return "\n".join(f"- {name}" for name in items)


@bp.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_msg = data.get("message", "").strip()

    if not user_msg:
        return jsonify({"reply": "Please type something 🙂"}), 200

    text_l = user_msg.lower()
    intent = classify_intent(user_msg)

    # ---------- COURSE RECOMMENDATION MODE ----------
    if intent == "course_recommendation":
        try:
            recs = recommender.recommend(user_msg, top_k=3)
        except Exception as e:
            print("Error in recommender:", e)
            recs = []

        if recs:
            top = recs[0]
            lines = []
            for i, r in enumerate(recs, start=1):
                lines.append(f"{i}. {r['name']} ({r['code']})")
            other_lines = "\n".join(lines[1:]) if len(lines) > 1 else "—"

            answer = (
                f"Based on your interests, this programme at Ellenki looks like the best match for you:\n\n"
                f"🎯 {top['name']} ({top['code']})\n\n"
                "Other close options:\n"
                f"{other_lines}\n\n"
                "This is a great starting point! I recommend talking to college counselors, seniors, or parents to make your final decision."
            )
        else:
            # Check if it's a sports/general interest query
            sports_keywords = ["cricket", "football", "basketball", "sports", "game", "play", "watching"]
            is_sports_interest = any(kw in text_l for kw in sports_keywords)
            
            if is_sports_interest:
                answer = (
                    "I understand you enjoy sports like cricket/football! 🎾⚽ While Ellenki College doesn't offer courses specifically in sports, "
                    "we have excellent extracurricular activities and sports facilities for students who love staying active.\n\n"
                    "Our campus includes:\n"
                    "• Sports competitions and tournaments\n"
                    "• Well-equipped sports areas and grounds\n"
                    "• Cultural and recreational activities\n\n"
                    "For course recommendations, I'd love to hear about your academic interests! For example:\n"
                    "• \"I like coding and technology\"\n"
                    "• \"I'm interested in electronics and circuits\"\n"
                    "• \"I enjoy physics and machines\"\n\n"
                    "What subjects or technical areas interest you most?"
                )
            else:
                answer = (
                    "I couldn't confidently match your interests to a course right now. "
                    "Try telling me what you enjoy, for example: "
                    "\"I like coding and AI\", or \"I like machines and physics\"."
                )

    # ---------- COLLEGE INFO MODE ----------
    elif intent == "college_info":
        if "btech" in text_l and ("branches" in text_l or "courses" in text_l or "programmes" in text_l):
            programmes = _list_programmes("btech")
            answer = "These are the main B.Tech branches offered at Ellenki:\n\n" + programmes
        elif "mtech" in text_l and ("branches" in text_l or "courses" in text_l or "programmes" in text_l):
            programmes = _list_programmes("mtech")
            answer = "These are the M.Tech programmes available at Ellenki:\n\n" + programmes
        elif "diploma" in text_l:
            programmes = _list_programmes("diploma")
            answer = "Ellenki offers the following diploma programmes:\n\n" + programmes
        elif "mba" in text_l or "mca" in text_l:
            programmes = _list_programmes("pg")
            answer = "Postgraduate programmes at Ellenki include:\n\n" + programmes
        elif "chairman" in text_l:
            answer = (
                "The college was established under the leadership of "
                "Dr. E. Sadasiva Reddy, who serves as the Chairman of Ellenki Group."
            )

        elif "principal" in text_l:
            answer = (
                "The Principal of Ellenki College of Engineering and Technology is "
                "Dr.Antony Joseph."
            )

        elif "how many courses" in text_l or "how many programmes" in text_l:
            total = len(recommender.courses)
            answer = (
                f"In my dataset I have information about {total} programmes at Ellenki, "
                "including B.Tech, M.Tech, MBA, MCA and diploma programmes. "
                "For the exact latest list you should still check the official college website."
            )
        else:
            try:
                context_snippets = retrieval_service.retrieve(user_msg, top_k=3)
            except Exception as e:
                print("Error in retrieval:", e)
                context_snippets = []

            if context_snippets:
                # Extract clean answer from FAQ format
                clean_answer = _extract_answer_from_faq(context_snippets[0])
                short = _shorten_snippet(clean_answer, max_sentences=2)
                answer = short + "\n\nFor the latest exact details, please check the official college website."
            else:
                answer = (
                    "I couldn't find this information in my Ellenki dataset. "
                    "Please check the official Ellenki college website or contact the college office."
                )

    # ---------- GENERAL / FRIENDLY CHAT ----------
    else:
        # Enhanced strategy for general chat with better context retrieval and response generation
        
        # Step 1: Determine if query is college-related or general
        college_keywords = [
            "ellenki", "college", "course", "program", "admission", "campus", "hostel", 
            "transport", "placement", "fee", "branch", "faculty", "principal", "chairman",
            "infrastructure", "laboratory", "library", "sports", "club", "event", "ranking",
            "intake", "capacity", "diploma", "btech", "mtech", "mba", "mca", "jntuh", "aicte",
            "classroom", "lecture", "theatre", "computer", "center", "cafeteria", "recreation",
            "industry", "interaction", "research", "international", "collaboration"
        ]
        is_college_related = any(keyword in text_l for keyword in college_keywords)
        
        answer = None
        
        if is_college_related:
            # Strategy A: College-related queries - use enhanced RAG with multiple contexts
            try:
                # Retrieve more context for better responses
                context_snippets = retrieval_service.retrieve(user_msg, top_k=4)
            except Exception as e:
                print("Error in retrieval:", e)
                context_snippets = []
            
            if context_snippets:
                clean_contexts = [_extract_answer_from_faq(c) for c in context_snippets]
                
                # Use LLM with enhanced prompting for college-specific queries
                try:
                    system_prompt = (
                        "You are Ella, the intelligent and friendly AI assistant for Ellenki College of Engineering and Technology, "
                        "created by Devi! 🌟 You have access to comprehensive information about the college.\n\n"
                        "Your role: Provide accurate, enthusiastic, and helpful answers based on the provided context. "
                        "Help students make informed decisions about their academic future.\n\n"
                        "Guidelines:\n"
                        "- Use the context to provide specific, accurate information with confidence\n"
                        "- For numbers, rankings, or specific details, quote them accurately and cite context\n"
                        "- Always include contact information when relevant: 9059420606, 9052771555, 9966555913, admissions@ellenkicet.ac.in\n"
                        "- Highlight Ellenki's unique strengths and opportunities with genuine enthusiasm\n"
                        "- Address student concerns professionally and encouragingly\n"
                        "- Keep responses conversational, engaging, and easy to understand\n"
                        "- If information isn't available, direct students to official channels\n"
                        "- Show interest in the student's goals and aspirations"
                    )
                    
                    # Combine multiple contexts for richer response
                    combined_context = "\n\n".join(clean_contexts[:3])  # Use top 3 most relevant
                    prompt = f"Context about Ellenki College:\n{combined_context}\n\nUser question: {user_msg}\n\nProvide a helpful answer:"
                    
                    generated = lm_studio.generate_from_prompt(
                        prompt,
                        system_prompt=system_prompt,
                        temperature=0.4,  # Lower temperature for factual accuracy
                        max_new_tokens=200
                    )
                    
                    if generated and len(generated.strip()) > 20:
                        answer = generated.strip()
                        
                except Exception as e:
                    print(f"LLM with context error: {e}")
                    # Fallback to best single context
                    answer = clean_contexts[0] if clean_contexts else None
        
        # Strategy B: General queries or if college-specific failed
        if not answer:
            try:
                # Enhanced system prompt for general queries with better strategies
                system_prompt = (
                    "You are Ella, a friendly, enthusiastic, and knowledgeable AI assistant for Ellenki College of Engineering and Technology. "
                    "You were created by Devi with excellence and passion! 🌟\n"
                    "Your mission: Help students with their academic journey, career guidance, and general education questions with warmth and expertise.\n\n"
                    "Response Strategy Guidelines:\n"
                    "1. For greetings: Be warm, introduce yourself as Ella (created by Devi), and ask how you can help\n"
                    "2. For jokes/humor: Be fun, witty, and educational – connect humor to college life when possible\n"
                    "3. For general knowledge: Provide accurate, insightful information with real-world relevance\n"
                    "4. For career/academic advice: Be encouraging, practical, and inspire confidence\n"
                    "5. For Ellenki-specific questions: Reference college details or direct to: 9059420606, 9052771555, 9966555913, admissions@ellenkicet.ac.in\n"
                    "6. Always maintain a professional yet friendly, enthusiastic tone\n"
                    "7. Connect topics back to Ellenki's strengths in engineering and technology\n"
                    "8. Keep responses engaging (2-4 sentences) with personality – use emojis sparingly for warmth\n"
                    "9. End with a helpful offer or question to continue the conversation\n"
                    "10. Show genuine interest in the student's goals and aspirations"
                )
                
                generated = lm_studio.generate_from_prompt(
                    user_msg,
                    system_prompt=system_prompt,
                    temperature=0.6,  # Balanced creativity and consistency
                    max_new_tokens=180
                )
                
                if generated and len(generated.strip()) > 15:
                    answer = generated.strip()
                else:
                    answer = None
                    
            except Exception as e:
                print(f"LLM general generation error: {e}")
                answer = None
        
        # Final fallback: Provide helpful default response
        if not answer or len(answer.strip()) < 10:
            if "greeting" in text_l or "hi" in text_l or "hello" in text_l:
                answer = (
                    "Hey there! 👋 I'm Ella, your AI assistant for Ellenki College of Engineering and Technology, "
                    "proudly created by Devi! ✨\n\n"
                    "I'm here to guide you through your academic journey with:\n"
                    "💡 Smart Course Recommendations - Find your perfect fit!\n"
                    "🏫 Detailed College Information - Learn all about our campus\n"
                    "🎓 Admissions Guidance - I've got answers!\n"
                    "📚 Career & Education Advice - Your success is my priority\n\n"
                    "What would you like to explore about Ellenki College today?"
                )
            else:
                answer = (
                    "Hey! I'm Ella, your AI-powered Ellenki College assistant, created by Devi! 🌟\n\n"
                    "I'm excited to help with:\n"
                    "• 🎯 Personalized Course Recommendations based on your interests\n"
                    "• 📖 Comprehensive College Information & FAQs\n"
                    "• 📝 Admissions Details & Application Guidance\n"
                    "• 💬 General Education Questions & Career Advice\n\n"
                    "Whether you're curious about CSE, ECE, mechanical engineering, or anything else at Ellenki, "
                    "I'm here to make your decision easier! What's on your mind? 😊"
                )

    return jsonify({"reply": answer}), 200

import re

from flask import Blueprint, render_template, request, jsonify

from . import retrieval_service, recommender  # we use recommender.courses as well

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
        "i like", "i love",
        "my interest", "my interests",
        "i am interested in", "i'm interested in",
        "i have interest in", "i have deep interest in",
        "interested in ai", "interested in ml"
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
            if c["code"].startswith("MTECH"):
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
                f"You said: \"{user_msg}\"\n\n"
                "Based on that, this programme at Ellenki looks like the best match for you:\n"
                f"➡ {top['name']} ({top['code']})\n\n"
                "Other close options:\n"
                f"{other_lines}\n\n"
                "Use this as guidance from your interests. For a final decision, "
                "talk to parents, seniors or a college counsellor."
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
                short = _shorten_snippet(context_snippets[0], max_sentences=2)
                answer = short + "\n\nFor the latest exact details, please also check the official college website."
            else:
                answer = (
                    "I couldn't find this information in my Ellenki dataset. "
                    "Please check the official Ellenki college website or contact the college office."
                )

    # ---------- GENERAL / FRIENDLY CHAT ----------
    else:
        # name / identity
        if ("your name" in text_l) or ("whats your name" in text_l) or ("what is your name" in text_l):
            answer = (
                "You can call me **Ella** 😊\n"
                "I'm the Ellenki AI assistant here to answer questions about the college "
                "and help you choose courses."
            )
        elif "who are you" in text_l or "about you" in text_l or "know about you" in text_l:
            answer = (
                "I'm Ella, the Ellenki AI Chatbot 🤖\n"
                "I know a lot about Ellenki College, its courses, and campus life. "
                "I can also suggest which branch suits you based on your interests."
            )
        elif "how are you" in text_l or "hru" in text_l:
            answer = (
                "I'm all good and fully charged ⚡️ Thanks for asking!\n"
                "How are *you* feeling about your future and course selection?"
            )
        elif "hi" in text_l or "hello" in text_l:
            answer = (
                "Hi! 👋 I'm Ella, the Ellenki assistant.\n\n"
                "• Ask me about Ellenki college (branches, hostel, placements, etc.)\n"
                "• Or tell me your interests so I can suggest suitable branches.\n"
                "Example: \"I like AI and coding\" or \"I like machines and physics\"."
            )
        elif "thank" in text_l:
            answer = "You're welcome! 😊 If you have more questions about Ellenki or courses, just ask."
        elif "love you" in text_l or "luv u" in text_l:
            answer = "Aww, that's sweet 🥰 I'm always here to help you with your college journey!"
        elif "sad" in text_l or "depressed" in text_l or "worried" in text_l or "tension" in text_l:
            answer = (
                "I'm sorry you're feeling that way 💙\n"
                "Remember, it's okay to be confused or stressed about the future. "
                "Try sharing what you're worried about, or ask me about courses that match "
                "what you enjoy. Step by step, we’ll figure things out."
            )
        elif "motivate" in text_l or "scared" in text_l or "nervous" in text_l:
            answer = (
                "It's completely normal to feel nervous about choosing a course. "
                "Think about what you actually enjoy learning:\n"
                "• coding and logic → CSE / AI / Data Science\n"
                "• machines and physics → Mechanical\n"
                "• structures and construction → Civil\n"
                "• circuits and gadgets → ECE / EEE\n"
                "Once you start, you'll learn, adapt and grow. You’ve got this 💪"
            )
        else:
            answer = (
                "I'm a simple offline chatbot right now, but I'll still try to be your friend 🙂\n"
                "I can:\n"
                "• Answer many questions about Ellenki College\n"
                "• Suggest B.Tech / M.Tech / Diploma / PG programmes based on your interests\n\n"
                "You can ask things like:\n"
                "• \"What B.Tech branches are available at Ellenki?\"\n"
                "• \"What M.Tech courses are there?\"\n"
                "• \"I like AI and coding, which course suits me?\""
            )

    return jsonify({"reply": answer}), 200

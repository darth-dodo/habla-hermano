"""Ten scripted demo conversations across all four languages and every level.

Written straight into LangGraph checkpoints with ``aupdate_state`` (no LLM
call), so they load exactly like real chats: same encrypted serializer, same
thread rows. Replies follow the app's level rules: A0 mostly English, B1
mostly target language, and each thread corrects one realistic mistake.
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from src.agent.checkpointer import get_checkpointer
from src.agent.graph import build_graph
from src.db.encryption import encrypt_field

# (language, level, title, days ago, [(learner, Hermano), ...])
CONVERSATIONS: list[tuple[str, str, str, int, list[tuple[str, str]]]] = [
    ("es", "A0", "Saludos y presentaciones", 25, [
        ("hola", "¡Hola! That means hello. Nice start! Now tell me your name. In Spanish you say **Me llamo...** (My name is...). For example: *Me llamo Ana.*"),
        ("me llamo Demo", "¡Muy bien! *Me llamo Demo* = My name is Demo. A new phrase: **Mucho gusto** means nice to meet you. Mucho gusto, Demo! Can you say it back?"),
        ("mucho gusto", "¡Excelente! That was your first Spanish conversation. Next time: **Soy de...** (I am from...)."),
    ]),
    ("es", "A1", "Mi familia", 18, [
        ("Hola, tengo un hermano y una hermana. Mi hermano se llama Luis y es alto.", "¡Hola! Qué bien, una familia grande. Tu frase es perfecta. ¿Y tu hermana? ¿Cómo se llama? ¿Es alta o baja?"),
        ("Mi hermana se llama Sofía. Ella es baja y muy simpático.", "¡Muy bien! Una pequeña corrección: *simpática*, con **a**, porque hablamos de Sofía. Los adjetivos cambian: *simpático* (él), *simpática* (ella). ¿Vives con tu familia?"),
        ("Vivo solo en un apartamento pequeño, pero visito a mi familia los domingos.", "¡Perfecto! *Visito a mi familia los domingos* suena muy natural. ¿Qué comen juntos los domingos?"),
    ]),
    ("es", "A2", "Un fin de semana en Valencia", 11, [
        ("Este fin de semana voy a ir a la playa con mis amigos. ¿Qué me recomiendas hacer en Valencia?", "¡Qué buen plan! En Valencia tienes que probar la paella, allí nació. También puedes alquilar una bici y pasear por el Jardín del Turia. ¿Vais en tren o en coche?"),
        ("Vamos en tren. El sábado pasado fui a Madrid y el tren fue muy rápido.", "¡Muy bien usado el pretérito! *Fui* (de **ir**, I went) y *fue* (de **ser**, it was) son iguales, ¡qué curioso! ¿Qué hiciste en Madrid?"),
        ("Visité el museo del Prado y comí churros con chocolate.", "¡Qué envidia! El Prado es increíble. ¿Qué cuadro te gustó más?"),
    ]),
    ("es", "B1", "Trabajar desde casa", 4, [
        ("Llevo dos años trabajando desde casa y, aunque me gusta, a veces echo de menos a mis compañeros.", "Te entiendo. *Echar de menos* está muy bien usado, es justo lo que diría un nativo. ¿Qué extrañas más: las charlas del café o colaborar en persona?"),
        ("Las charlas del café. Si mi empresa tendría una oficina cerca, iría dos días por semana.", "Buena reflexión. Un detalle: después de *si* va el imperfecto de subjuntivo: *Si mi empresa **tuviera** una oficina cerca, iría dos días por semana.* La segunda parte está perfecta. ¿Crees que el trabajo híbrido es el futuro?"),
        ("Creo que sí, aunque depende mucho del tipo de trabajo y de cada persona.", "Totalmente de acuerdo, y ya argumentas con matices. ¿Cómo organizas tu día para no sentirte aislado?"),
    ]),
    ("de", "A1", "Mein Wochenende", 15, [
        ("Hallo! Am Samstag ich gehe ins Kino mit meiner Freundin.", "Hallo! Schöner Plan! Kleine Korrektur: *Am Samstag **gehe ich** ins Kino.* Im Deutschen steht das Verb an zweiter Stelle. Welchen Film möchtet ihr sehen?"),
        ("Wir möchten einen Komödie sehen. Danach essen wir Pizza.", "Super! Fast perfekt: *eine Komödie*, weil es *die Komödie* heißt. *Danach essen wir Pizza* ist genau richtig, Verb an zweiter Stelle! Isst du lieber Pizza oder Pasta?"),
    ]),
    ("de", "A2", "Beim Arzt", 7, [
        ("Guten Tag, ich habe seit drei Tagen Kopfschmerzen und ich kann nicht gut schlafen.", "Oh, das tut mir leid! Dein Satz ist sehr gut. Der Arzt fragt jetzt vielleicht: *Haben Sie auch Fieber?* Was antwortest du?"),
        ("Nein, ich habe kein Fieber, aber ich bin sehr müde. Ich habe viel gearbeitet letzte Woche.", "Gut gemacht, *kein Fieber* ist richtig! Im Perfekt steht das Partizip am Ende: *Ich habe letzte Woche viel **gearbeitet**.* Der Arzt sagt: *Sie brauchen Ruhe.* Möchtest du noch etwas fragen?"),
        ("Muss ich Tabletten nehmen?", "Perfekte Frage! Antwort: *Nehmen Sie bei Bedarf eine Tablette, aber nicht mehr als drei pro Tag.* *Bei Bedarf* heißt: wenn du sie brauchst. Gute Besserung!"),
    ]),
    ("fr", "A0", "Au café", 21, [
        ("bonjour", "Bonjour! That means hello. Let's order at a café. Say **Je voudrais...** (I would like...). Try: *Je voudrais un café.*"),
        ("je voudrais un café", "Très bien! Now add **s'il vous plaît** (please). The waiter asks: *Avec du lait?* (With milk?) Answer **oui** (yes) or **non** (no)."),
        ("oui s'il vous plaît", "Parfait! You just ordered a café au lait. When you leave, say **Merci, au revoir!** (Thank you, goodbye!)"),
    ]),
    ("fr", "B1", "Souvenirs de voyage", 2, [
        ("L'année dernière, j'ai voyagé au Japon pendant trois semaines. C'était le meilleur voyage de ma vie.", "Quelle chance! Passé composé pour l'action, imparfait pour la description, exactement ce qu'il faut. Qu'est-ce qui t'a le plus marqué là-bas?"),
        ("La gentillesse des gens. Si je pourrais, je retournerais là-bas chaque année.", "C'est beau. Petite correction: après *si*, on met l'imparfait: *Si je **pouvais**, je retournerais là-bas chaque année.* Le conditionnel *retournerais* est parfait. Tu préfères voyager seul ou accompagné?"),
        ("Je préfère voyager seul, parce que je peux changer mes plans quand je veux.", "Très bon argument, et très naturel. Quelle est ta prochaine destination de rêve?"),
    ]),
    ("hi", "A0", "Namaste! First words", 23, [
        ("namaste", "Namaste! Great start, that is the most common greeting. Next, ask how someone is: **Aap kaise hain?** (How are you? polite). Try it!"),
        ("aap kaise hain?", "Bahut accha! (Very good!) The usual answer is **Main theek hoon** (I am fine). Add **shukriya** (thank you): *Main theek hoon, shukriya.*"),
        ("main theek hoon shukriya", "Perfect! A full Hinglish exchange. Next we can learn **Mera naam ... hai** (My name is ...)."),
    ]),
    ("hi", "A1", "Chai aur office", 0, [
        ("Main roz office jaata hoon aur subah chai peeta hoon.", "Wah, bahut badiya! *Roz* (every day) and *jaata hoon* (I go) are spot on. Many people mix it: *Main daily office jaata hoon*, Hinglish at its best. Chai mein kya daalte ho? Adrak (ginger) ya elaichi (cardamom)?"),
        ("Main chai mein adrak daalta hoon. Office mein meeting bahut hai.", "Nice, *adrak wali chai* is a classic! Small fix: many meetings, so plural: *Office mein bahut **meetings hain**.* Use *hain* for plural, *hai* for singular. Aaj kitni meetings hain?"),
    ]),
]  # fmt: skip


def thread_rows(user_id: str, now: datetime) -> list[dict[str, Any]]:
    """One conversation_threads row per conversation, dated in the past. Pure."""
    rows = []
    for i, (language, level, title, days_ago, _) in enumerate(CONVERSATIONS):
        created = now - timedelta(days=days_ago, hours=1 + i % 3)
        rows.append(
            {
                "user_id": user_id,
                "thread_id": f"user:{user_id}:{uuid.uuid4()}",
                "title": encrypt_field(title) or title,
                "language": language,
                "level": level,
                "created_at": created.isoformat(),
                "updated_at": (created + timedelta(minutes=6 + i)).isoformat(),
            }
        )
    return rows


async def seed_conversations(admin: Any, user_id: str, now: datetime) -> int:
    """Replace the user's conversations with the scripted ones. Returns how many.

    Old checkpoints must already be gone (delete_user_rows); this removes the
    old thread rows, writes the checkpoints, then the rows, so the sidebar
    never lists a thread without messages.
    """
    rows = thread_rows(user_id, now)
    await asyncio.to_thread(
        lambda: admin.table("conversation_threads").delete().eq("user_id", user_id).execute()
    )
    async with get_checkpointer() as checkpointer:
        graph = build_graph(checkpointer=checkpointer)
        for row, (language, level, _, _, turns) in zip(rows, CONVERSATIONS, strict=True):
            messages: list[HumanMessage | AIMessage] = []
            for learner, hermano in turns:
                messages += [HumanMessage(content=learner), AIMessage(content=hermano)]
            await graph.aupdate_state(
                RunnableConfig(configurable={"thread_id": row["thread_id"]}),
                {"messages": messages, "language": language, "level": level, "user_id": user_id},
                as_node="analyze",
            )
    await asyncio.to_thread(lambda: admin.table("conversation_threads").insert(rows).execute())
    return len(rows)

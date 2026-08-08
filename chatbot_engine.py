import json
import numpy as np
from sentence_transformers import SentenceTransformer, util
import os
from datetime import date

# ---- Import your reservation models ----
# Adjust the import path according to your project structure
from classes.reservation import load_reservation_by_id, load_all_reservations # pyright: ignore[reportMissingImports]


def _calculate_age(birth_date):
    """Return age in years from birth_date (date object)."""
    if not birth_date:
        return None
    today = date.today()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))


class FAQChatbot:
    def __init__(self, knowledge_path):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.knowledge = []            # list of dicts: {"question": ..., "answer": ...}
        self.questions = []
        self.load_knowledge(knowledge_path)
        self.embeddings = self.model.encode(self.questions, convert_to_tensor=True)

    def load_knowledge(self, path):
        if not os.path.exists(path):
            raise FileNotFoundError(f"Knowledge base not found: {path}")
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.knowledge = data
        self.questions = [item['question'] for item in data]

    def retrieve_context(self, user_input, top_k=3):
        """
        Returns a string of the top_k most relevant Q&A pairs,
        filtered by a minimum similarity score.
        """
        if not self.knowledge:
            return ""

        query_embedding = self.model.encode(user_input, convert_to_tensor=True)
        cos_scores = util.cos_sim(query_embedding, self.embeddings)[0]
        top_indices = np.argsort(-cos_scores.cpu().numpy())[:top_k]

        contexts = []
        for idx in top_indices:
            score = float(cos_scores[idx])
            if score < 0.6:   # ignore weak matches
                continue
            entry = self.knowledge[idx]
            contexts.append(f"Q: {entry['question']}\nA: {entry['answer']}")
        return "\n\n".join(contexts)

    def get_response(self, user_input, threshold=0.5):
        """
        Simple retrieval-based answer (used as fallback).
        """
        query_embedding = self.model.encode(user_input, convert_to_tensor=True)
        cos_scores = util.cos_sim(query_embedding, self.embeddings)[0]
        best_idx = int(cos_scores.argmax())
        best_score = float(cos_scores[best_idx])

        if best_score >= threshold:
            return self.knowledge[best_idx]['answer']
        else:
            return "I'm sorry, I couldn't find that information. Please email support@autohire.com."

    def build_contextual_prompt(self, user_message, user, gps_data=None, reservation=None):
        """
        Build a system prompt that includes dynamic user data.
        """
        base = (
            "You are AutoHire's helpful customer support assistant. "
            "Use the following dynamic information about the user to answer their question. "
            "If the user asks for specific data (like car location, balance, reservation status), "
            "use the provided context. If the answer is not in the context, say you don't know "
            "and suggest contacting support@autohire.com.\n\n"
        )

        context_parts = []

        if user:
            context_parts.append(f"User name: {user.get_name()}")
            context_parts.append(f"User email: {user.get_email()}")
            context_parts.append(f"User balance: {user.get_balance()} PKR")
            if user.get_birth_date():
                age = _calculate_age(user.get_birth_date())
                context_parts.append(f"User age: {age} years")

        # Active or pending reservation
        active_id = user.get_active_reservation() if user else None
        if active_id:
            res = load_reservation_by_id(active_id)
            if res:
                context_parts.append(f"Active reservation ID: {res.get_id()}")
                context_parts.append(f"Car VIN: {res.get_car_vin()}")
                context_parts.append(f"Rental period: {res.get_start_date()} to {res.get_end_date()}")
                context_parts.append(f"Pickup location: {res.get_pickup_location()}")
                context_parts.append(f"Return location: {res.get_return_location()}")
                context_parts.append(f"Reservation status: {res.get_status()}")
                if gps_data:
                    context_parts.append(
                        f"Car current GPS: lat={gps_data.get('lat')}, lng={gps_data.get('lng')}, "
                        f"last updated={gps_data.get('updated_at')}"
                    )
        else:
            # Check for pending reservation
            pending = [
                r for r in load_all_reservations()
                if r.user_email == user.get_email() and r.status == 'pending'
            ]
            if pending:
                context_parts.append(
                    f"You have a pending reservation (ID: {pending[0].get_id()}) waiting for admin approval."
                )

        # Extra context from FAQ knowledge base (optional)
        faq_context = self.retrieve_context(user_message, top_k=2)
        if faq_context:
            context_parts.append(f"\nGeneral FAQ knowledge:\n{faq_context}")

        full_prompt = base + "\n".join(context_parts)
        return full_prompt
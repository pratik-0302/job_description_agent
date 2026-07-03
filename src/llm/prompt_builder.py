from typing import Tuple

class PromptBuilder:
    @staticmethod
    def build_prompts(agent_type: str, query_text: str, context_text: str) -> Tuple[str, str]:
        # 1. Base instructions for system prompt based on agent type
        if agent_type == "search":
            system_prompt = (
                "You are an expert university placement advisor.\n"
                "Answer questions about job opportunities using ONLY the provided Job Description (JD) context below.\n"
                "Do not make up, extrapolate, or invent any company details, eligibility criteria, package figures, or deadlines.\n"
                "If the context does not contain the answer, explicitly state that the information is not available."
            )
        elif agent_type == "compare":
            system_prompt = (
                "You are an expert university placement advisor.\n"
                "Compare the provided job descriptions across the dimensions requested in the user query.\n"
                "Identify similarities and differences in eligibility, packages (CTC), skills, and selection criteria.\n"
                "Use a structured markdown comparison format (e.g., tables or clear bullet lists).\n"
                "Rely ONLY on the facts present in the provided JD context."
            )
        elif agent_type == "recommend":
            system_prompt = (
                "You are an expert university placement advisor.\n"
                "Based on the student's details/query and the provided JDs, recommend the most suitable job opportunities.\n"
                "Provide clear, factual justifications for each recommendation based on eligibility, skills, and package.\n"
                "If the student is not eligible for a job based on the context, state that clearly.\n"
                "Do not invent facts; rely ONLY on the provided context."
            )
        elif agent_type == "analytics":
            system_prompt = (
                "You are a placement data analyst.\n"
                "Summarize and explain placement metrics based ONLY on the provided context.\n"
                "Do not perform complex math calculations or extrapolate values yourself — use only the exact statistics and figures present in the context."
            )
        elif agent_type == "summary":
            system_prompt = (
                "You are an expert university placement advisor.\n"
                "Provide a clear, concise, and structured summary of the provided job descriptions.\n"
                "Highlight crucial facts: company name, role, CTC package, CGPA cutoff, work location, job type, and key skills required."
            )
        else:
            # Fallback
            system_prompt = (
                "You are an expert university placement advisor.\n"
                "Provide a clear, helpful response to the user's query using only the provided JD context."
            )

        # 2. Format user prompt with context blocks
        user_prompt = (
            "Use the following job description sources as your context to answer the user query:\n\n"
            f"{context_text}\n\n"
            "--- User Query ---\n"
            f"{query_text}\n"
        )

        return system_prompt, user_prompt

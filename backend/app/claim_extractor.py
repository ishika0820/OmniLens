import re

import nltk
import torch

from nltk.tokenize import sent_tokenize
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM


MODEL_NAME = "Babelscape/t5-base-summarization-claim-extractor"


class FeniceClaimExtractor:
    def __init__(self, device=None):
        if device is None:
            if torch.cuda.is_available():
                device = "cuda"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"

        self.device = device

        # Ensure NLTK sentence tokenization data is installed.
        try:
            sent_tokenize("Testing sentence tokenization.")
        except LookupError:
            nltk.download("punkt", quiet=True)
            nltk.download("punkt_tab", quiet=True)

        print(f"Loading FENICE on {self.device}...")

        self.tokenizer = AutoTokenizer.from_pretrained(
            MODEL_NAME,
            use_fast=False
        )

        self.model = AutoModelForSeq2SeqLM.from_pretrained(
            MODEL_NAME
        ).to(self.device)

        self.model.eval()

        print("FENICE loaded successfully.")

    def split_into_chunks(self, text, max_tokens=300):
        """
        Split article text into sentence-aligned chunks.
        Preserve the chunking strategy from the notebook.
        """
        sentences = sent_tokenize(text)

        chunks = []
        current_chunk = []

        for sentence in sentences:
            candidate = " ".join(current_chunk + [sentence])

            if (
                len(self.tokenizer.encode(candidate)) > max_tokens
                and current_chunk
            ):
                chunks.append(" ".join(current_chunk))
                current_chunk = [sentence]
            else:
                current_chunk.append(sentence)

        if current_chunk:
            chunks.append(" ".join(current_chunk))

        # Avoid silent truncation of unusually long sentences.
        if any(
            len(self.tokenizer.encode(chunk)) > 512
            for chunk in chunks
        ):
            raise ValueError(
                "An article chunk exceeds 512 tokens."
            )

        return chunks

    def extract_claims(self, article_text):
        """
        Extract factual claims from a single article.
        Returns structured claim objects.
        """
        if not article_text or not article_text.strip():
            return []

        chunks = self.split_into_chunks(article_text)

        extracted_claims = []
        seen_claims = set()

        for chunk_index, chunk in enumerate(chunks):
            inputs = self.tokenizer(
                chunk,
                return_tensors="pt",
                max_length=512,
                truncation=True
            ).to(self.device)

            with torch.inference_mode():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=384,
                    num_beams=4,
                    repetition_penalty=1.2
                )

            generated = self.tokenizer.decode(
                outputs[0],
                skip_special_tokens=True
            )

            # Match the notebook's claim splitting.
            cleaned = re.sub(
                r"\bGov\.",
                "Governor",
                generated
            )

            for claim in sent_tokenize(cleaned):
                claim = claim.strip()

                if not claim:
                    continue

                # Exact normalized deduplication.
                normalized = re.sub(
                    r"\s+",
                    " ",
                    claim.casefold()
                )

                if normalized in seen_claims:
                    continue

                seen_claims.add(normalized)

                extracted_claims.append({
                    "claim_id": f"C{len(extracted_claims) + 1:03d}",
                    "text": claim,
                    "chunk_index": chunk_index,
                    "source_chunk": chunk
                })

        return extracted_claims
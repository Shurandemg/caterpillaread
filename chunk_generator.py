import logging
import re
from typing import List, Tuple, Optional
import spacy
from config import (
    CHUNK_SIZE_MIN, CHUNK_SIZE_MAX, MAX_MESSAGES,
    SPACY_MODEL_EN, SPACY_MODEL_RU
)

logger = logging.getLogger(__name__)

class ChunkGenerator:
    """Генератор смысловых кусков текста"""
    
    def __init__(self, language: str = 'auto'):
        """
        Инициализирует генератор
        :param language: 'ru' для русского, 'en' для английского, 'auto' для автоопределения
        """
        self.language = language
        self.nlp = self._load_nlp_model(language)
        self.sent_splitter = self._load_sent_splitter(language)
    
    def _load_nlp_model(self, language: str) -> Optional[spacy.Language]:
        """Загружает spaCy модель для языка"""
        try:
            if language == 'ru':
                model_name = SPACY_MODEL_RU
            elif language == 'en':
                model_name = SPACY_MODEL_EN
            else:
                return None
            
            nlp = spacy.load(model_name)
            logger.info(f"Loaded spaCy model: {model_name}")
            return nlp
        except OSError:
            logger.warning(f"spaCy model not found: {model_name}. Install with: python -m spacy download {model_name}")
            return None
    
    def _load_sent_splitter(self, language: str):
        """Загружает разбиватель предложений"""
        if language == 'ru':
            return RussianSentenceSplitter()
        elif language == 'en':
            return EnglishSentenceSplitter()
        else:
            return GenericSentenceSplitter()
    
    def split_into_sentences(self, text: str) -> List[str]:
        """
        Разбивает текст на предложения
        :param text: исходный текст
        :return: список предложений
        """
        if self.nlp:
            try:
                doc = self.nlp(text[:1000000])  # Ограничение для больших текстов
                sentences = [sent.text.strip() for sent in doc.sents if sent.text.strip()]
                return sentences
            except Exception as e:
                logger.warning(f"Error in spaCy sentence splitting: {e}")
        
        # Fallback на регулярные выражения
        return self.sent_splitter.split(text)
    
    def generate_chunks(self, text: str) -> List[str]:
        """
        Генерирует куски текста оптимального размера
        :param text: исходный текст
        :return: список кусков
        """
        # Разбиваем на параграфы
        paragraphs = text.split('\n\n')
        chunks = []
        current_chunk = ""
        
        for paragraph in paragraphs:
            # Удаляем лишние пробелы в параграфе
            paragraph = ' '.join(paragraph.split())
            
            if not paragraph.strip():
                continue
            
            # Если добавление этого параграфа превысит лимит
            potential_chunk = (current_chunk + " " + paragraph).strip()
            
            if len(potential_chunk) > CHUNK_SIZE_MAX:
                # Текущий кусок достаточно большой, сохраняем его
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = paragraph
                else:
                    # Параграф сам больше чем максимум, разбиваем его
                    sub_chunks = self._split_large_paragraph(paragraph)
                    chunks.extend(sub_chunks)
            else:
                current_chunk = potential_chunk
        
        # Добавляем последний кусок
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        # Проверяем размеры и объединяем маленькие куски
        chunks = self._merge_small_chunks(chunks)
        
        # Вычищаем и валидируем куски
        chunks = [self._validate_chunk(chunk) for chunk in chunks if chunk.strip()]
        
        logger.info(f"Generated {len(chunks)} chunks from text")
        return chunks
    
    def _split_large_paragraph(self, text: str) -> List[str]:
        """Разбивает большой параграф на куски по предложениям"""
        sentences = self.split_into_sentences(text)
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            potential = (current_chunk + " " + sentence).strip()
            
            if len(potential) > CHUNK_SIZE_MAX:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = sentence
                else:
                    # Само предложение больше лимита (редко)
                    chunks.append(sentence)
                    current_chunk = ""
            else:
                current_chunk = potential
        
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _merge_small_chunks(self, chunks: List[str]) -> List[str]:
        """Объединяет маленькие куски с соседними"""
        if not chunks:
            return []
        
        merged = []
        current = chunks[0]
        
        for i in range(1, len(chunks)):
            potential = (current + " " + chunks[i]).strip()
            
            if len(potential) <= CHUNK_SIZE_MAX:
                current = potential
            else:
                merged.append(current)
                current = chunks[i]
        
        merged.append(current)
        
        # Ещё раз фильтруем по минимальному размеру
        return [c for c in merged if len(c) >= CHUNK_SIZE_MIN or c in chunks]
    
    def _validate_chunk(self, text: str) -> str:
        """
        Валидирует кусок текста
        - Не рвет слова в конце
        - Завершает предложением
        """
        text = text.strip()
        
        # Удаляем незавершенное слово в конце
        if len(text) > 0:
            # Если последний символ не является пунктуацией, обрезаем до последнего полного слова
            if text[-1] not in '.!?\'"»:;–—':
                # Ищем последнее полное предложение
                for punct in ['.', '!', '?']:
                    last_punct = text.rfind(punct)
                    if last_punct > len(text) * 0.7:  # Если знак препинания в последних 30%
                        text = text[:last_punct + 1]
                        break
        
        return text.strip()
    
    def estimate_messages(self, chunks: List[str]) -> int:
        """
        Оценивает сколько сообщений будет отправлено
        Берет по 2 куска на сообщение или меньше если очень большие
        """
        if not chunks:
            return 0
        
        # Простая оценка: в среднем 2 куска на сообщение
        messages = (len(chunks) + 1) // 2
        return max(1, messages)


class RussianSentenceSplitter:
    """Разбиватель русских предложений"""
    
    def split(self, text: str) -> List[str]:
        """Разбивает текст на предложения по русским правилам"""
        # Регулярное выражение для русских предложений
        pattern = r'(?<=[.!?])\s+(?=[А-Яа-яЁё])'
        sentences = re.split(pattern, text)
        return [s.strip() for s in sentences if s.strip()]


class EnglishSentenceSplitter:
    """Разбиватель английских предложений"""
    
    def split(self, text: str) -> List[str]:
        """Разбивает текст на предложения по английским правилам"""
        # Регулярное выражение для английских предложений
        pattern = r'(?<=[.!?])\s+(?=[A-Z])'
        sentences = re.split(pattern, text)
        return [s.strip() for s in sentences if s.strip()]


class GenericSentenceSplitter:
    """Универсальный разбиватель предложений"""
    
    def split(self, text: str) -> List[str]:
        """Разбивает текст на предложения по универсальным правилам"""
        # Базовое разбиение по точкам, восклицательным и вопросительным знакам
        pattern = r'(?<=[.!?])\s+'
        sentences = re.split(pattern, text)
        return [s.strip() for s in sentences if s.strip()]


def create_chunk_generator(language: str = 'auto') -> ChunkGenerator:
    """
    Фабрика для создания генератора кусков
    :param language: 'ru', 'en', или 'auto'
    :return: ChunkGenerator
    """
    return ChunkGenerator(language)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    # Пример использования
    test_text = """
    Это первый параграф текста. Он содержит несколько предложений.
    Вот второе предложение с точкой в конце.
    
    Это второй параграф. Он немного длиннее первого.
    Здесь могут быть разные идеи и мысли автора.
    И третье предложение в этом параграфе.
    """
    
    generator = create_chunk_generator('ru')
    chunks = generator.generate_chunks(test_text)
    
    for i, chunk in enumerate(chunks, 1):
        print(f"\n--- Chunk {i} ({len(chunk)} chars) ---")
        print(chunk)

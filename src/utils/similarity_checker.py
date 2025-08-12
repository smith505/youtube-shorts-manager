#!/usr/bin/env python3
"""
Similarity checker for detecting duplicate movie facts/topics.
Uses multiple techniques to identify semantically similar titles.
"""

import re
from typing import Set, Tuple, List
from difflib import SequenceMatcher


class SimilarityChecker:
    """Check for semantic similarity between movie facts/titles."""
    
    @staticmethod
    def normalize_text(text: str) -> str:
        """Normalize text for comparison by removing minor variations."""
        text = text.lower().strip()
        
        # Remove punctuation except for parentheses (which contain years)
        text = re.sub(r'[,\.\!\?\-\:]', '', text)
        
        # Normalize whitespace
        text = ' '.join(text.split())
        
        return text
    
    @staticmethod
    def extract_movie_and_fact(title: str) -> Tuple[str, str]:
        """Extract the movie/show name and the fact from a title."""
        # Pattern to match "In MovieName (Year), fact..."
        pattern = r'^in\s+(.+?\s*\(\d{4}\)),?\s*(.+)$'
        match = re.match(pattern, title.lower())
        
        if match:
            movie = match.group(1).strip()
            fact = match.group(2).strip()
            return movie, fact
        
        # Alternative pattern without "In" prefix
        pattern2 = r'^(.+?\s*\(\d{4}\)),?\s*(.+)$'
        match = re.match(pattern2, title.lower())
        
        if match:
            movie = match.group(1).strip()
            fact = match.group(2).strip()
            return movie, fact
        
        return "", title.lower().strip()
    
    @staticmethod
    def extract_key_elements(fact: str) -> Set[str]:
        """Extract key elements from a fact for comparison."""
        # Remove common words and extract significant terms
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'was', 'were', 'is', 'are', 'been',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
            'should', 'may', 'might', 'must', 'can', 'this', 'that', 'these',
            'those', 'then', 'than', 'so', 'as', 'her', 'his', 'their', 'our'
        }
        
        # Tokenize and filter
        words = fact.lower().split()
        key_words = set()
        
        for word in words:
            # Clean word
            word = re.sub(r'[^a-z0-9]', '', word)
            if word and word not in stop_words and len(word) > 2:
                key_words.add(word)
        
        return key_words
    
    @staticmethod
    def extract_topic_category(fact: str) -> str:
        """Extract the general topic/category from a fact for broader similarity detection."""
        fact_lower = fact.lower()
        
        # Define topic categories with their keywords
        categories = {
            'acting_performance': ['acting', 'performance', 'role', 'character', 'portrayed', 'played', '演技'],
            'improvisation': ['improvised', 'improvisation', 'ad-lib', 'ad lib', 'spontaneous', 'unscripted'],
            'choreography_dance': ['choreographed', 'dance', 'dancing', 'moves', 'sequence', 'routine'],
            'stunts_action': ['stunts', 'stunt', 'action', 'fight', 'martial arts', 'combat'],
            'real_life_based': ['real life', 'based on', 'true story', 'actually happened', 'real person'],
            'method_acting': ['method', 'stayed in character', 'immersed', 'preparation', 'research'],
            'physical_transformation': ['gained weight', 'lost weight', 'transformation', 'physical', 'body'],
            'injury_accident': ['injured', 'hurt', 'accident', 'broke', 'fractured', 'hospital'],
            'director_choice': ['director', 'directed', 'filmmaker', 'chose', 'decided', 'vision'],
            'casting_audition': ['cast', 'casting', 'audition', 'chosen', 'selected', 'hired'],
            'dialogue_script': ['dialogue', 'lines', 'script', 'wrote', 'rewrote', 'changed'],
            'music_soundtrack': ['music', 'soundtrack', 'song', 'composed', 'score'],
            'special_effects': ['cgi', 'effects', 'green screen', 'practical', 'makeup'],
            'production_behind': ['production', 'filming', 'shot', 'created', 'made', 'budget'],
            'easter_eggs': ['easter egg', 'hidden', 'reference', 'cameo', 'tribute'],
        }
        
        # Check which category this fact belongs to
        for category, keywords in categories.items():
            if any(keyword in fact_lower for keyword in keywords):
                return category
        
        return 'general'  # Default category
    
    @staticmethod
    def are_facts_similar(fact1: str, fact2: str, threshold: float = 0.6) -> bool:
        """
        Check if two facts are semantically similar with stricter detection.
        Uses multiple similarity metrics and topic categorization.
        """
        # Normalize facts
        norm_fact1 = SimilarityChecker.normalize_text(fact1)
        norm_fact2 = SimilarityChecker.normalize_text(fact2)
        
        # Quick exact match check
        if norm_fact1 == norm_fact2:
            return True
        
        # Check if they're in the same topic category
        category1 = SimilarityChecker.extract_topic_category(fact1)
        category2 = SimilarityChecker.extract_topic_category(fact2)
        
        # If same category, be more strict about similarity
        category_threshold = threshold
        if category1 == category2 and category1 != 'general':
            category_threshold = 0.4  # Much more strict for same category
        
        # Extract key elements
        key_words1 = SimilarityChecker.extract_key_elements(fact1)
        key_words2 = SimilarityChecker.extract_key_elements(fact2)
        
        # Calculate Jaccard similarity of key words
        if key_words1 and key_words2:
            intersection = key_words1.intersection(key_words2)
            union = key_words1.union(key_words2)
            jaccard_sim = len(intersection) / len(union) if union else 0
            
            # Use category-adjusted threshold
            if jaccard_sim >= category_threshold:
                return True
        
        # Use sequence matching for similar phrasing
        sequence_sim = SequenceMatcher(None, norm_fact1, norm_fact2).ratio()
        if sequence_sim >= 0.75:  # Slightly lower but still high threshold
            return True
        
        # Enhanced pattern matching for common similar topics
        patterns_to_check = [
            # Dance/choreography patterns
            (r'choreograph\w*\s+.*danc\w*', r'choreograph\w*\s+.*danc\w*'),
            (r'danc\w*\s+.*choreograph\w*', r'danc\w*\s+.*choreograph\w*'),
            # Improvisation patterns
            (r'improvisd?\w*', r'improvisd?\w*'),
            (r'ad[\s-]?libb?\w*', r'ad[\s-]?libb?\w*'),
            (r'unscripted', r'spontaneous'),
            # Acting method patterns
            (r'method\s+act\w*', r'stayed.*character'),
            (r'immersed.*role', r'preparation.*character'),
            # Physical transformation
            (r'gained.*weight', r'lost.*weight'),
            (r'physical.*transformation', r'body.*change'),
            # Real life patterns
            (r'real\s+(?:life\s+)?(?:actual\s+)?', r'based.*true'),
            (r'(?:actually\s+)?(?:really\s+)?happen\w*', r'true.*story'),
            # Stunt patterns
            (r'own.*stunts?', r'did.*stunts?'),
            (r'stunt.*work', r'action.*sequence'),
            # Injury patterns
            (r'injured.*filming', r'hurt.*set'),
            (r'broke.*during', r'fractured.*while'),
        ]
        
        for pattern1, pattern2 in patterns_to_check:
            match1 = re.search(pattern1, norm_fact1)
            match2 = re.search(pattern2, norm_fact2)
            if match1 and match2:
                # Both facts contain similar special patterns
                # Check if they're about the same subject with lower threshold
                if jaccard_sim >= 0.3:  # Much lower threshold when patterns match
                    return True
        
        return False
    
    @staticmethod
    def check_movie_topic_diversity(new_title: str, existing_titles: Set[str], max_same_category: int = 2) -> Tuple[bool, str]:
        """
        Check if adding this title would create too many similar topics for the same movie.
        Returns (should_block, reason)
        """
        new_movie, new_fact = SimilarityChecker.extract_movie_and_fact(new_title)
        new_category = SimilarityChecker.extract_topic_category(new_fact)
        
        if not new_movie or new_category == 'general':
            return False, ""  # Don't block if we can't categorize
        
        # Count how many titles from same movie are in the same category
        same_movie_same_category = 0
        
        for existing_title in existing_titles:
            existing_movie, existing_fact = SimilarityChecker.extract_movie_and_fact(existing_title)
            
            if existing_movie and SimilarityChecker.normalize_text(new_movie) == SimilarityChecker.normalize_text(existing_movie):
                existing_category = SimilarityChecker.extract_topic_category(existing_fact)
                if existing_category == new_category:
                    same_movie_same_category += 1
        
        if same_movie_same_category >= max_same_category:
            return True, f"Too many {new_category.replace('_', ' ')} facts for {new_movie}"
        
        return False, ""

    @staticmethod
    def is_duplicate_title(new_title: str, existing_titles: Set[str]) -> Tuple[bool, str]:
        """
        Enhanced duplicate detection with topic diversity checking.
        Returns (is_duplicate, similar_title_if_found)
        """
        new_movie, new_fact = SimilarityChecker.extract_movie_and_fact(new_title)
        
        # First check for topic diversity (prevent too many similar topics for same movie)
        should_block, reason = SimilarityChecker.check_movie_topic_diversity(new_title, existing_titles)
        if should_block:
            return True, reason
        
        # Then check for similar facts
        for existing_title in existing_titles:
            existing_movie, existing_fact = SimilarityChecker.extract_movie_and_fact(existing_title)
            
            # Only check facts from the same movie/show
            if new_movie and existing_movie:
                if SimilarityChecker.normalize_text(new_movie) == SimilarityChecker.normalize_text(existing_movie):
                    # Same movie, check if facts are similar
                    if SimilarityChecker.are_facts_similar(new_fact, existing_fact):
                        return True, existing_title
            else:
                # No movie identified, check full title similarity
                if SimilarityChecker.are_facts_similar(new_title, existing_title):
                    return True, existing_title
        
        return False, ""
    
    @staticmethod
    def filter_duplicate_titles(new_titles: List[str], existing_titles: Set[str]) -> Tuple[List[str], List[Tuple[str, str]]]:
        """
        Filter out duplicate titles from a list of new titles.
        Returns (unique_titles, list_of_duplicates_with_similar_existing)
        """
        unique_titles = []
        duplicates = []
        
        # Also check for duplicates within the new titles themselves
        all_titles_to_check = existing_titles.copy()
        
        for title in new_titles:
            title = title.strip()
            if not title:
                continue
            
            is_dup, similar_to = SimilarityChecker.is_duplicate_title(title, all_titles_to_check)
            
            if is_dup:
                duplicates.append((title, similar_to))
            else:
                unique_titles.append(title)
                all_titles_to_check.add(title)
        
        return unique_titles, duplicates
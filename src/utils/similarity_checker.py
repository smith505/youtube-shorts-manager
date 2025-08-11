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
    def are_facts_similar(fact1: str, fact2: str, threshold: float = 0.7) -> bool:
        """
        Check if two facts are semantically similar.
        Uses multiple similarity metrics.
        """
        # Normalize facts
        norm_fact1 = SimilarityChecker.normalize_text(fact1)
        norm_fact2 = SimilarityChecker.normalize_text(fact2)
        
        # Quick exact match check
        if norm_fact1 == norm_fact2:
            return True
        
        # Extract key elements
        key_words1 = SimilarityChecker.extract_key_elements(fact1)
        key_words2 = SimilarityChecker.extract_key_elements(fact2)
        
        # Calculate Jaccard similarity of key words
        if key_words1 and key_words2:
            intersection = key_words1.intersection(key_words2)
            union = key_words1.union(key_words2)
            jaccard_sim = len(intersection) / len(union) if union else 0
            
            # High overlap of key terms indicates similar facts
            if jaccard_sim >= threshold:
                return True
        
        # Use sequence matching for similar phrasing
        sequence_sim = SequenceMatcher(None, norm_fact1, norm_fact2).ratio()
        if sequence_sim >= 0.8:  # High threshold for sequence similarity
            return True
        
        # Check for specific patterns that indicate the same fact
        # (e.g., "choreographed her own dance" vs "choreographed her dance")
        patterns_to_check = [
            (r'choreograph\w*\s+\w+\s+(?:own\s+)?(?:viral\s+)?danc\w+', 
             r'choreograph\w*\s+\w+\s+(?:own\s+)?(?:viral\s+)?danc\w+'),
            (r'improvisd?\w*', r'improvisd?\w*'),
            (r'ad[\s-]?libb?\w*', r'ad[\s-]?libb?\w*'),
            (r'real\s+(?:life\s+)?(?:actual\s+)?', r'real\s+(?:life\s+)?(?:actual\s+)?'),
            (r'(?:actually\s+)?(?:really\s+)?happen\w*', r'(?:actually\s+)?(?:really\s+)?happen\w*'),
        ]
        
        for pattern1, pattern2 in patterns_to_check:
            if (re.search(pattern1, norm_fact1) and re.search(pattern2, norm_fact2)):
                # Both facts contain similar special patterns
                # Check if they're about the same subject
                if jaccard_sim >= 0.5:  # Lower threshold when patterns match
                    return True
        
        return False
    
    @staticmethod
    def is_duplicate_title(new_title: str, existing_titles: Set[str]) -> Tuple[bool, str]:
        """
        Check if a new title is a duplicate of any existing title.
        Returns (is_duplicate, similar_title_if_found)
        """
        new_movie, new_fact = SimilarityChecker.extract_movie_and_fact(new_title)
        
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
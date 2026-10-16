"""The listener server: the translation API.

Copyright (C) 2025-2026 Ga Hing Woo (Jiaxing Hu)

This file is part of EzySpeech.

EzySpeech is free software: you can redistribute it and/or modify it under
the terms of the GNU Affero General Public License as published by the Free
Software Foundation, either version 3 of the License, or (at your option)
any later version. Two additional terms apply under section 7: the author
attribution in the about dialog must be preserved, and no trademark rights
are granted. See LICENSE and TRADEMARK.md.

EzySpeech is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License for more
details.
"""

from app.user.core import *  # noqa: F401,F403  (one namespace, split by subject)

# ──────────────────────────────────────────
# Translation API with Rate Limiting and Caching
# ──────────────────────────────────────────
from app.services.translation import get_translation_service  # noqa: E402

@app.route('/api/translate', methods=['POST'])
@limiter.limit("300 per minute")  # 5 requests per second per client (need headroom for bulk imports)
@check_client_access
def translate_text():
    """
    Translate text from server-side
    
    Request:
        {
            "text": "text to translate",
            "target_lang": "zh",  # target language code
        }
    
    Response:
        {
            "success": true/false,
            "translated": "translated text",
            "original": "original text",
            "target_lang": "zh",
            "source_lang": "auto",
            "cached": true/false,  # true if from cache
            "error": "error message (if failed)"
        }
    """
    try:
        data = request.json or {}
    except Exception:
        security_logger.warning(f"Malformed JSON from {get_client_key()}")
        return jsonify({'success': False, 'error': 'Invalid request'}), 400
    
    text = sanitize_text(data.get('text', ''), max_length=5000)
    target_lang = sanitize_text(data.get('target_lang', 'en'), max_length=20)
    room_id = normalize_room_id(data.get('room') or request.args.get('room'))

    if not text or not target_lang:
        return jsonify({
            'success': False,
            'error': 'Missing required fields: text, target_lang'
        }), 400

    if len(text) > 5000:
        return jsonify({
            'success': False,
            'error': 'Text too long (max 5000 characters)'
        }), 413

    try:
        # Get translation service instance
        translation_service = get_translation_service()

        # Fetch glossary entries matching this room+language (if DB enabled)
        glossary_terms = _get_glossary_for(room_id, target_lang)

        # Perform translation - now returns (success, translated, from_cache)
        success, translated, from_cache = translation_service.translate(
            text, target_lang, glossary=glossary_terms
        )

        return jsonify({
            'success': success,
            'translated': translated,
            'original': text,
            'target_lang': target_lang,
            'source_lang': 'auto',
            'cached': from_cache,
            'room_id': room_id,
            'glossary_applied': len(glossary_terms) if glossary_terms else 0,
            'error': None if success else 'Translation failed'
        })
    
    except Exception as e:
        logger.error(f"Translation error: {e}")
        return jsonify({
            'success': False,
            'error': f'Translation service error: {str(e)}'
        }), 500

@app.route('/api/translate/batch', methods=['POST'])
@limiter.limit("60 per minute")  # 1 request per second per client for batch
@check_client_access
def translate_batch():
    """
    Translate multiple texts in batch
    
    Request:
        {
            "texts": ["text1", "text2", ...],
            "target_lang": "zh"
        }
    
    Response:
        {
            "success": true/false,
            "translations": [
                {
                    "original": "text1",
                    "translated": "translated text1",
                    "success": true,
                    "cached": false
                },
                ...
            ],
            "error": "error message (if failed)"
        }
    """
    try:
        data = request.json or {}
    except Exception:
        security_logger.warning(f"Malformed JSON from {get_client_key()}")
        return jsonify({'success': False, 'error': 'Invalid request'}), 400
    
    texts = data.get('texts', [])
    target_lang = sanitize_text(data.get('target_lang', 'en'), max_length=20)
    room_id = normalize_room_id(data.get('room') or request.args.get('room'))

    if not isinstance(texts, list) or not texts or not target_lang:
        return jsonify({
            'success': False,
            'error': 'Invalid request: expected texts (list) and target_lang'
        }), 400
    
    # Limit batch size
    if len(texts) > 50:
        return jsonify({
            'success': False,
            'error': 'Batch too large (max 50 items)'
        }), 413
    
    try:
        translation_service = get_translation_service()
        glossary_terms = _get_glossary_for(room_id, target_lang)
        results = []
        
        for text in texts:
            sanitized = sanitize_text(text, max_length=5000)
            if not sanitized:
                results.append({
                    'original': text,
                    'translated': text,
                    'success': False,
                    'cached': False,
                    'error': 'Empty or invalid text'
                })
                continue
            
            success, translated, from_cache = translation_service.translate(
                sanitized, target_lang, glossary=glossary_terms
            )
            results.append({
                'original': sanitized,
                'translated': translated,
                'success': success,
                'cached': from_cache,
                'error': None if success else 'Translation failed'
            })
        
        return jsonify({
            'success': True,
            'translations': results,
            'count': len(results),
            'room_id': room_id,
            'glossary_applied': len(glossary_terms) if glossary_terms else 0,
        })
    
    except Exception as e:
        logger.error(f"Batch translation error: {e}")
        return jsonify({
            'success': False,
            'error': f'Batch translation failed: {str(e)}'
        }), 500

@app.route('/api/translate/cache', methods=['POST'])
@limiter.limit("10 per minute")
@require_auth
@check_client_access
def clear_translation_cache():
    """Clear translation cache"""
    try:
        translation_service = get_translation_service()
        translation_service.clear_cache()
        logger.info(f"Translation cache cleared by {request.user.get('username')}")
        return jsonify({'success': True, 'message': 'Cache cleared'})
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

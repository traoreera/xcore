from typing import Callable, Dict, List, Any, Optional
import asyncio
import logging
import inspect
from functools import wraps

logger = logging.getLogger(__name__)

class HookManager:
    def __init__(self):
        # Stocke les fonctions : {"nom_evenement": [func1, func2]}
        self._hooks: Dict[str, List[Callable]] = {}
        self._priorities: Dict[str, List[int]] = {}  # Pour gérer l'ordre d'exécution
        
    def register(self, event_name: str, func: Callable, priority: int = 50):
        """
        Un plugin s'enregistre pour écouter un événement.
        
        Args:
            event_name: Nom de l'événement
            func: Fonction callback (sync ou async)
            priority: Priorité (0-100, plus petit = exécuté en premier)
        """
        if event_name not in self._hooks:
            self._hooks[event_name] = []
            self._priorities[event_name] = []
        
        # Insertion triée par priorité
        idx = 0
        for i, p in enumerate(self._priorities[event_name]):
            if priority < p:
                idx = i
                break
            idx = i + 1
        
        self._hooks[event_name].insert(idx, func)
        self._priorities[event_name].insert(idx, priority)
        
        logger.debug(f"Hook registered: {event_name} -> {func.__name__} (priority: {priority})")
    
    def unregister(self, event_name: str, func: Callable):
        """Retire un hook spécifique."""
        if event_name in self._hooks:
            try:
                idx = self._hooks[event_name].index(func)
                self._hooks[event_name].pop(idx)
                self._priorities[event_name].pop(idx)
                logger.debug(f"Hook unregistered: {event_name} -> {func.__name__}")
            except ValueError:
                logger.warning(f"Hook not found: {event_name} -> {func.__name__}")
    
    async def emit(self, event_name: str, **kwargs) -> List[Any]:
        """
        Déclenche un événement et retourne les résultats.
        
        Args:
            event_name: Nom de l'événement
            **kwargs: Arguments passés aux hooks
            
        Returns:
            Liste des résultats de chaque hook
        """
        if event_name not in self._hooks:
            logger.debug(f"No hooks for event: {event_name}")
            return []
        
        results = []
        tasks = []
        
        for func in self._hooks[event_name]:
            try:
                # Support des fonctions sync et async
                if inspect.iscoroutinefunction(func):
                    tasks.append(func(**kwargs))
                else:
                    # Wrap sync functions
                    tasks.append(asyncio.to_thread(func, **kwargs))
            except Exception as e:
                logger.error(f"Error preparing hook {func.__name__} for {event_name}: {e}")
        
        # Exécution avec gestion d'erreurs
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Log des erreurs
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                func_name = self._hooks[event_name][i].__name__
                logger.error(f"Hook {func_name} failed for {event_name}: {result}")
        
        return results
    
    async def emit_until_handled(self, event_name: str, **kwargs) -> Optional[Any]:
        """
        Exécute les hooks séquentiellement jusqu'à ce qu'un retourne une valeur non-None.
        Utile pour les chaînes de responsabilité.
        """
        if event_name not in self._hooks:
            return None
        
        for func in self._hooks[event_name]:
            try:
                if inspect.iscoroutinefunction(func):
                    result = await func(**kwargs)
                else:
                    result = await asyncio.to_thread(func, **kwargs)
                
                if result is not None:
                    logger.debug(f"Event {event_name} handled by {func.__name__}")
                    return result
            except Exception as e:
                logger.error(f"Hook {func.__name__} failed for {event_name}: {e}")
        
        return None
    
    def list_hooks(self, event_name: Optional[str] = None) -> Dict[str, List[str]]:
        """Liste tous les hooks enregistrés."""
        if event_name:
            return {event_name: [f.__name__ for f in self._hooks.get(event_name, [])]}
        return {evt: [f.__name__ for f in funcs] for evt, funcs in self._hooks.items()}
    
    def decorator(self, event_name: str, priority: int = 50):
        """Décorateur pour enregistrer facilement des hooks."""
        def wrapper(func: Callable):
            self.register(event_name, func, priority)
            return func
        return wrapper
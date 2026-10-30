/* Asyncify yields through a browser task rather than clamped nested timers. */
EM_ASYNC_JS(void,port_browser_yield,(),{await Module.portBrowserYield();});

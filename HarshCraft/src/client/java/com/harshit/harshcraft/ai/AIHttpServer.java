package com.harshit.harshcraft.ai;

import com.google.gson.Gson;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import net.minecraft.client.Minecraft;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.function.Supplier;

/**
 * Local HTTP bridge between the Python bot and the Minecraft client.
 *
 *   GET  /ping          -> {"ok":true,"in_world":bool}
 *   GET  /observation   -> full observation
 *   POST /step          -> body = action JSON; blocks until the action finished
 *   GET  /scan?names=a,b&r=24&v=12&max=64 -> blocks whose id contains a fragment
 *
 * Every access to Minecraft state is marshalled onto the client thread.
 */
public class AIHttpServer {

    public static final int PORT = 5000;

    private final AIEnvironment env;
    private final Minecraft mc;
    private final Gson gson = new Gson();
    private HttpServer server;

    public AIHttpServer(AIEnvironment env, Minecraft mc) {
        this.env = env;
        this.mc = mc;
    }

    public void start() throws IOException {
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", PORT), 0);
        server.setExecutor(Executors.newFixedThreadPool(4));
        server.createContext("/ping", ex -> safe(ex, this::ping));
        server.createContext("/observation", ex -> safe(ex, this::observation));
        server.createContext("/step", ex -> safe(ex, this::step));
        server.createContext("/scan", ex -> safe(ex, this::scan));
        server.start();
        System.out.println("HarshCraft AI bridge listening on http://127.0.0.1:" + PORT);
    }

    public void stop() {
        if (server != null) {
            server.stop(0);
        }
    }

    /* ------------------------------------------------------------------ */

    private interface Handler {
        JsonObject handle(HttpExchange ex) throws Exception;
    }

    private void safe(HttpExchange ex, Handler h) throws IOException {
        JsonObject out;
        try {
            out = h.handle(ex);
        } catch (Throwable t) {
            out = AIEnvironment.error(t.getClass().getSimpleName() + ": " + t.getMessage());
        }
        byte[] bytes = gson.toJson(out).getBytes(StandardCharsets.UTF_8);
        ex.getResponseHeaders().set("Content-Type", "application/json");
        ex.sendResponseHeaders(200, bytes.length);
        try (OutputStream os = ex.getResponseBody()) {
            os.write(bytes);
        }
    }

    /** Run on the Minecraft client thread and wait for the result. */
    private JsonObject onMain(Supplier<JsonObject> s) throws Exception {
        CompletableFuture<JsonObject> f = new CompletableFuture<>();
        mc.execute(() -> {
            try {
                f.complete(s.get());
            } catch (Throwable t) {
                f.completeExceptionally(t);
            }
        });
        return f.get(10, TimeUnit.SECONDS);
    }

    private JsonObject ping(HttpExchange ex) throws Exception {
        return onMain(() -> {
            JsonObject o = new JsonObject();
            o.addProperty("ok", true);
            o.addProperty("in_world", mc.player != null && mc.level != null);
            o.addProperty("paused", mc.isPaused());
            return o;
        });
    }

    private JsonObject observation(HttpExchange ex) throws Exception {
        return onMain(env::observe);
    }

    private JsonObject step(HttpExchange ex) throws Exception {
        String body = new String(ex.getRequestBody().readAllBytes(), StandardCharsets.UTF_8);
        JsonObject action = JsonParser.parseString(body).getAsJsonObject();
        int ticks = action.has("ticks") ? action.get("ticks").getAsInt() : 1;
        CompletableFuture<CompletableFuture<JsonObject>> handle = new CompletableFuture<>();
        mc.execute(() -> {
            try {
                handle.complete(env.submit(action));
            } catch (Throwable t) {
                handle.completeExceptionally(t);
            }
        });
        CompletableFuture<JsonObject> done = handle.get(10, TimeUnit.SECONDS);
        long waitMs = 15000L + ticks * 100L;
        try {
            return done.get(waitMs, TimeUnit.MILLISECONDS);
        } catch (java.util.concurrent.TimeoutException te) {
            mc.execute(env::stopAction);
            return AIEnvironment.error("step_timeout (is the game paused? press F3+P to disable pause-on-lost-focus)");
        }
    }

    private JsonObject scan(HttpExchange ex) throws Exception {
        String q = ex.getRequestURI().getRawQuery();
        String names = "";
        int r = 24;
        int v = 12;
        int max = 64;
        if (q != null) {
            for (String kv : q.split("&")) {
                String[] p = kv.split("=", 2);
                if (p.length < 2) {
                    continue;
                }
                String val = java.net.URLDecoder.decode(p[1], StandardCharsets.UTF_8);
                switch (p[0]) {
                    case "names": names = val; break;
                    case "r": r = Math.min(40, Integer.parseInt(val)); break;
                    case "v": v = Math.min(24, Integer.parseInt(val)); break;
                    case "max": max = Math.min(256, Integer.parseInt(val)); break;
                    default: break;
                }
            }
        }
        List<String> frags = new ArrayList<>();
        for (String n : names.split(",")) {
            if (!n.isBlank()) {
                frags.add(n.trim());
            }
        }
        final int fr = r;
        final int fv = v;
        final int fm = max;
        return onMain(() -> env.scan(frags, fr, fv, fm));
    }
}

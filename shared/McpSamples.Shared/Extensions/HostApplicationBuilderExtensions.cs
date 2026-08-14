using System.Reflection;

using Microsoft.AspNetCore.Builder;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

namespace McpSamples.Shared.Extensions;

/// <summary>
/// This represents the extension entity for <see cref="IHostApplicationBuilder"/>.
/// </summary>
public static class HostApplicationBuilderExtensions
{
    /// <summary>
    /// Builds the application with the specified <paramref name="useStreamableHttp"/> option.
    /// </summary>
    /// <param name="builder"><see cref="IHostApplicationBuilder"/> instance.</param>
    /// <param name="useStreamableHttp">Value indicating whether to use streamable HTTP or not.</param>
    /// <returns>Returns the <see cref="IHost"/> instance.</returns>
    public static IHost BuildApp(this IHostApplicationBuilder builder, bool useStreamableHttp)
    {
        // Route all ILogger output to stderr so the JSON-RPC stream on stdout
        // stays clean (fixes "Failed to parse message" warnings in VS Code).
        builder.Logging.AddConsole(o => o.LogToStandardErrorThreshold = LogLevel.Trace);

        if (useStreamableHttp == true)
        {
            builder.Services.AddMcpServer()
                            .WithHttpTransport(o => o.Stateless = true)
                            .WithPromptsFromAssembly(Assembly.GetEntryAssembly())
                            .WithResourcesFromAssembly(Assembly.GetEntryAssembly())
                            .WithToolsFromAssembly(Assembly.GetEntryAssembly());

            var webApp = (builder as WebApplicationBuilder)!.Build();

            // Disable HTTPS redirection in development environment to avoid issues with self-signed certificates
            if (!webApp.Environment.IsDevelopment())
            {
                webApp.UseHttpsRedirection();
            }

            webApp.MapMcp("/mcp");

            return webApp;
        }

        builder.Services.AddMcpServer()
                        .WithStdioServerTransport()
                        .WithPromptsFromAssembly(Assembly.GetEntryAssembly())
                        .WithResourcesFromAssembly(Assembly.GetEntryAssembly())
                        .WithToolsFromAssembly(Assembly.GetEntryAssembly());

        var consoleApp = (builder as HostApplicationBuilder)!.Build();

        return consoleApp;
    }
}
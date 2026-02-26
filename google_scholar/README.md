# Google Scholar MCP Server
> Project originate from here: https://github.com/mochow13/google-scholar-mcp

Enable AI assistants to search, access, and get Google Scholar articles through a simple MCP interface.

The Google Scholar Server provides a bridge between AI assistants and Google Scholar's vast collection of research papers and articles through the Model Context Protocol (MCP).
It allows AI models to search for articles and papers, access their metadata, and perform some analysis in a programmatic way.


## Container 
We build the container using a reference to a SHA on the origin git path.  
```dockerfile
...
# Clone the repository
ARG REPO_URL=https://github.com/mochow13/google-scholar-mcp.git
ARG BRANCH=main
# This here sha was the one that was main when we adopted the MCP server. 
ARG COMMIT_SHA=258b00a80f7f17cbe9a3227c488a519674fd3869
RUN git clone --depth 1 --branch ${BRANCH} ${REPO_URL} .
# reset to known version of the MCP server.
RUN git reset --hard ${COMMIT_SHA}
...
```

## Testing
When the MCP is running and added as a tool to the Supervisor the following examples can be used for checking that things is running as they should.
```text
Query: Find recent papers about machine learning in healthcare

[Called tool search_google_scholar with args {"query":"machine learning healthcare recent"}]

Based on the search results, here are some recent papers about machine learning in healthcare:

1. "Deep Learning Applications in Medical Imaging" - This paper explores...
2. "Predictive Analytics in Patient Care" - Research on using ML for...
...

Query: What about specifically for diagnostic imaging?

[Called tool search_google_scholar with args {"query":"machine learning diagnostic imaging healthcare"}]

Here are papers specifically focused on diagnostic imaging applications:
...
```
If one wants to try the server locally there is in the original repository a client that can be used for exploration.  
Check the original README.md for more information: [README.md](https://github.com/mochow13/google-scholar-mcp?tab=readme-ov-file#running-the-client)

## License

This project is licensed under the MIT License.


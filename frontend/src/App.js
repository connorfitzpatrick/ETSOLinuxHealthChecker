// App.js
import "./App.css";
import TextBox from "./components/TextBox/textbox";
import React, { useEffect, useState } from "react";
import ServerTab from "./components/ServerTab/serverTab";
import ServerDetailsTable from "./components/Table/serverDetailsTable";
import { v4 as uuidv4 } from "uuid";

const App = () => {
  const [results, setResults] = useState([]);
  const [connectionId, setConnectionId] = useState(null);
  useEffect(() => {
    const newConnectionId = uuidv4();
    setConnectionId(newConnectionId);
  }, []);

  useEffect(() => {
    console.log("Results updated:", results);
  }, [results]);

  const handleSubmit = async (serverList) => {
    const serverNames = serverList.split(/\r?\n/);
    // Establish session with connectionID
    try {
      const response = await fetch("http://localhost:8000/establish_session", {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
          // Send connection ID in headers
          "X-Connection-ID": connectionId,
        },
      });
    } catch (error) {
      console.error("Failed to establish session:", error);
    }

    // Initialize results state with server names after successful POST
    const initialResults = serverNames.map((serverName) => ({
      serverName,
      status: {
        overall_state: "Loading",
        ping_status: "",
        general_info: {
          date: "",
          uptime: "",
          users: "",
          load_average: "",
          operating_system_name: "",
        },
        inode_info: {
          inode_health_status: "",
          inode_issues: [],
          inode_data: [],
        },
        filesystem_info: {
          filesystem_health_status: "",
          filesystem_issues: [],
          filesystem_data: [],
        },
        cpu_use_info: {
          cpu_use_health_status: "",
          cpu_use_issues: [],
          cpu_use_data: [],
        },
        ntp_info: {
          ntp_health_status: "",
        },
        server_issues: {},
        logs: [],
      },
    }));
    setResults(initialResults);

    // Establish an EventSource connection for receiving server events
    const eventSource = new EventSource(
      `http://localhost:8000/process_servers/?id=${connectionId}`
    );

    // POST server names
    try {
      const response = fetch("http://localhost:8000/process_servers/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          // Send connection ID in headers
          "X-Connection-ID": connectionId,
        },
        body: JSON.stringify({ serverNames }),
      });

      eventSource.onmessage = (event) => {
        const eventData = JSON.parse(event.data);
        console.log(eventData);
        setResults((prevResults) =>
          prevResults.map((server) =>
            server.serverName === eventData.server
              ? {
                  ...server,
                  status: eventData.status,
                }
              : server
          )
        );
        console.log(eventData);
      };

      eventSource.onerror = (error) => {
        console.error("EventSource error:", error);
        eventSource.close();
      };

      // Clean up EventSource when component unmounts or connectionId changes
      return () => {
        eventSource.close();
      };
    } catch (error) {
      console.error("Error sending POST request:", error);
    }
  };

  return (
    <div className="App">
      <h1>Linux Server Health Checker</h1>
      <div className="container">
        <TextBox onSubmit={handleSubmit} />
      </div>
      {results.length > 0 && (
        <>
          <div className="output-container">
            {results.map((server) => (
              <ServerTab
                key={server.serverName}
                serverName={server.serverName}
                serverInfo={server.status}
              />
            ))}
          </div>
          <div className="table-container">
            <ServerDetailsTable serverInfo={results} />
          </div>
        </>
      )}
    </div>
  );
};

export default App;

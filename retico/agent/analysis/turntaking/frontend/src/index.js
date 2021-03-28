import React from "react";
import ReactDOM from "react-dom";
import { Route, Switch, BrowserRouter as Router } from "react-router-dom";
import Navbar from "react-bootstrap/Navbar";
import Nav from "react-bootstrap/Nav";

import Interaction from "./Interaction";
import Information from "./Information";

import "bootstrap/dist/css/bootstrap.min.css";
import "./index.css";

const Navigation = (props) => {
	return (
		<Navbar bg="dark" expand="sm" variant="dark">
			<Navbar.Brand href="/">TurnTaking</Navbar.Brand>
			<Nav className="mr-auto">
				<Nav.Link href="/Interaction">Interactions</Nav.Link>
				<Nav.Link href="/Information">Information</Nav.Link>
			</Nav>
		</Navbar>
	);
};

const Home = (props) => {
	return (
		<div>
			<h1>UI</h1>
			<ol>
				<li> Aggregation </li>
				<ol>
					<li> Switch root directory. Upper navigation? </li>
				</ol>
				<li> Interaction Turns </li>
				<ol>
					<li> turn audio waveform </li>
					<li> Show total trp for each token on last recognized utterance </li>
				</ol>
			</ol>
			<h1>System</h1>
			<ol>
				<li>Baseline agent-turn-end correct but prediction isnt?</li>
				<li>Timestamps on recognized words</li>
				<li>Custom ASR. </li>
				<li>Custom TTS. Eva etc</li>
			</ol>
			<h1>Bots</h1>
			<ol>
				<li>LMBot/BlenderBot</li>
				<li>Repeat Bot</li>
				<ol>
					<li>User actual audio</li>
					<li>User words with TTS</li>
				</ol>
				<li>Yes/No Bot</li>
				<ol>
					<li>
						ASR final time is quick yes resonses and no responses gets an added
						wait time.
					</li>
					<li>
						Short static baseline suitable for single utterance yes and no game.
					</li>
				</ol>
				<li>Eliza Bot</li>
			</ol>
		</div>
	);
};

const routes = (
	<Router>
		<div>
			<Navigation />
			<Switch>
				<Route exact path="/" component={Home} />
				<Route path="/Interaction" component={Interaction} />
				<Route path="/Information" component={Information} />
			</Switch>
		</div>
	</Router>
);

ReactDOM.render(routes, document.getElementById("root"));

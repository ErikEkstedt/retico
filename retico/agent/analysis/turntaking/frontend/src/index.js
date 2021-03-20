import React from 'react';
import ReactDOM from 'react-dom';
import { Route, Switch, BrowserRouter as Router } from 'react-router-dom'
import Navbar from 'react-bootstrap/Navbar';
import Nav from 'react-bootstrap/Nav';

import Aggregate from './Aggregate';
import Interaction from './Interaction';
import Information from './Information';

import 'bootstrap/dist/css/bootstrap.min.css';
import './index.css';


const Navigation = (props) => {
  return (
    <Navbar bg="dark" expand="sm" variant="dark">
      <Navbar.Brand href="/">TurnTaking</Navbar.Brand>
      <Nav className="mr-auto">
        <Nav.Link href="/Interaction">Interaction</Nav.Link>
        <Nav.Link href="/Aggregate">Aggregate</Nav.Link>
        <Nav.Link href="/Information">Information</Nav.Link>
      </Nav>
    </Navbar>
  );
};

const Home = (props) => {
  return (
    <div>
      <h1>TODO</h1>
      <ol>
        <li> Switch dialog file </li>
        <li> Global dialog stats </li>
        <li> Global root stats </li>
        <li> Fix dialog turn audio </li>
        <li> Add information as needed </li>
      </ol>
    </div>
  );
};

const routes = (
  <Router>
    <div>
      <Navigation/>
      <Switch >
        <Route exact path="/" component={Home} />
        <Route path="/Interaction" component={Interaction} />
        <Route path="/Aggregate" component={Aggregate} />
        <Route path="/Information" component={Information} />
      </Switch >
    </div>
  </Router>
);

ReactDOM.render(routes, document.getElementById('root'));

import React, { Component, useState } from "react";
import { Navbar, Nav, NavDropdown, Tab, Tabs } from 'react-bootstrap';

import Dialog from './Dialog'
import Annotation from './Annotation'
import ChatAgent from './ChatAgent'
import Global from './Global';

import './App.css';
import 'bootstrap/dist/css/bootstrap.min.css';


const interactionsURL = "/api/interactions";


const Navigation = (props) => {
  const [key, setKey] = useState('dialog');

  const items = props.interactions.map((s, i) => {
    return <NavDropdown.Item eventKey={s} key={i}> {s} </NavDropdown.Item>
  })

  return (
    <Navbar expand="sm">
      <Navbar.Collapse id="basic-navbar-nav">
        <Tabs
          activeKey={key}
          onSelect={(k) => {
            props.onChangeContent(k);
            setKey(k)
          }}
          className="mr-auto"
        >
          <Tab eventKey='dialog' title="Dialog" />
          <Tab eventKey='global' title="Global" />
          <Tab eventKey='annotation' title="Annotation" />
          <Tab eventKey='chatagent' title="Chat" />
        </Tabs >
        <Nav 
          activeKey={props.activeKey} 
          onSelect={(key) => props.onChangeInteraction(key)} 
          className="justify-content-end"
         >
          <NavDropdown 
            title="Interactions" 
            size="sm"
            drop='left'
          >
            {items}
          </NavDropdown>
        </Nav>
      </Navbar.Collapse>
    </Navbar>
  );
};


export default class Interaction extends Component {
  constructor(props) {
    super(props);
    this.state = {
      content: 'dialog',
      interaction: "",
      interactions: [],
      activeKeyDropdown: 0,
    };
    this.onChangeContent=this.onChangeContent.bind(this)
    this.onChangeInteraction=this.onChangeInteraction.bind(this)
  }

  componentDidMount() {
    fetch(interactionsURL).then(response => response.json()).then((data) => {
      this.setState({
        interactions: data.interactions,
        interaction: data.interactions[0],
      })
    })
  }

  onChangeContent(content) {
    this.setState({content: content});
  }

  onChangeInteraction(interaction) {
    console.log('interaction: '+ interaction)
    this.setState({
      interaction: interaction,
    });
  }

  getContent() {
    let content;
    if (this.state.content === 'global'){
      content = <Global interaction={this.state.interaction}  key={this.state.interaction}/>;
    } else if (this.state.content === 'annotation') {
      content = <Annotation />
    } else if (this.state.content === 'chatagent') {
      content = <ChatAgent />
    } else {
      content = <Dialog interaction={this.state.interaction} key={this.state.interaction}/>
    }
    return content
  }

  render () {
    // const content = this.getContent();
    return (
      <div>
        <Navigation 
          onChangeContent={this.onChangeContent} 
          onChangeInteraction={this.onChangeInteraction} 
          interactions={this.state.interactions} 
          activeKey={this.state.activeKeyDropdown}
        /> 
        <h4>{this.state.interaction}</h4>
        { this.getContent() }
      </div>
    );
  }
}
